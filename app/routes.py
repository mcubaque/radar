import hmac
import json
import os
import re
import time

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    render_template,
    request,
    send_from_directory,
    stream_with_context,
)

from app import media
from app.extensions import limiter
from app.flight import EMERGENCY_SQUAWKS, cells_for_bbox, haversine_km

bp = Blueprint("main", __name__)

ICAO24 = re.compile(r"[0-9a-fA-F]{6}")
WATCH_VALUE = re.compile(r"[A-Za-z0-9 ]{2,20}")
KEEPALIVE_S = 15


def public(f):
    return {k: v for k, v in f.items() if not k.startswith("_")}


def parse_bbox():
    """(lamin, lomin, lamax, lomax) de la query, o (None, respuesta de error)."""
    try:
        bbox = tuple(float(request.args[k]) for k in ("lamin", "lomin", "lamax", "lomax"))
    except (KeyError, ValueError):
        return None, (jsonify(error="Parametros lamin, lomin, lamax, lomax requeridos"), 400)
    if not (-90 <= bbox[0] < bbox[2] <= 90 and -180 <= bbox[1] < bbox[3] <= 180):
        return None, (jsonify(error="bbox invalido"), 400)
    if len(cells_for_bbox(bbox)) > current_app.config["MAX_CELLS"]:
        return None, (jsonify(error="Zona demasiado grande, acerca el mapa", code="too_large"), 400)
    return bbox, None


def require_db():
    if not current_app.db.enabled:
        return jsonify(error="Historial no disponible (sin base de datos)"), 503
    return None


def require_admin():
    token = current_app.config["ADMIN_TOKEN"]
    if token and not hmac.compare_digest(request.headers.get("X-Admin-Token", ""), token):
        return jsonify(error="No autorizado"), 401
    return None


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/sw.js")
def service_worker():
    response = send_from_directory(current_app.static_folder, "sw.js", mimetype="text/javascript")
    response.headers["Cache-Control"] = "no-cache"
    return response


@bp.route("/health")
@limiter.exempt
def health():
    store = current_app.store
    age = round(time.time() - store.last_cycle, 1) if store.last_cycle else None
    providers = current_app.chain.status()
    return jsonify(
        status="ok" if any(p["ok"] for p in providers) else "degraded",
        providers=providers,
        ingest={"flights": len(store.flights), "cells": len(store.cells), "last_cycle_age_s": age},
        database=current_app.db.enabled,
        static_data=current_app.static.ready,
    )


@bp.route("/api/config")
def config():
    cfg = current_app.config
    receiver = {"lat": cfg["RECEIVER_LAT"], "lon": cfg["RECEIVER_LON"], "range_km": cfg["RECEIVER_RANGE_KM"]} \
        if cfg["LOCAL_RECEIVER_URL"] else None
    return jsonify(
        min_zoom=cfg["MIN_ZOOM"], history=current_app.db.enabled, receiver=receiver,
        admin_required=bool(cfg["ADMIN_TOKEN"]), retention_days=cfg["RETENTION_DAYS"],
    )


# --- vuelos en vivo ---

@bp.route("/api/flights")
def flights():
    bbox, error = parse_bbox()
    if error:
        return error
    current_app.store.touch(cells_for_bbox(bbox))
    return jsonify([public(f) for f in current_app.store.in_bbox(bbox)])


@bp.route("/api/stream")
@limiter.limit("30 per minute")
def stream():
    """Server-Sent Events: foto inicial completa y luego solo los vuelos que cambian."""
    bbox, error = parse_bbox()
    if error:
        return error
    store = current_app.store
    cells = cells_for_bbox(bbox)

    def sse(event, data):
        return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"

    def generate():
        last_version, sent, first = 0, set(), True
        last_event = store.events[-1]["id"] if store.events else 0
        yield "retry: 3000\n\n"
        while True:
            store.touch(cells)
            version = store.wait(last_version, KEEPALIVE_S)
            if version == last_version:
                yield ": ping\n\n"
                continue
            current = store.in_bbox(bbox)
            ids = {f["id"] for f in current}
            changed = [public(f) for f in current if f["_v"] > last_version]
            gone = sorted(sent - ids)
            yield sse("flights", {"full": first, "flights": changed, "gone": gone, "errors": store.errors(cells)})
            for event in store.events_after(last_event):
                yield sse("alert", event)
                last_event = event["id"]
            sent, last_version, first = ids, version, False

    return Response(stream_with_context(generate()), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })


# --- detalle de un vuelo ---

@bp.route("/api/aircraft/<icao24>")
def aircraft(icao24):
    if not ICAO24.fullmatch(icao24):
        return jsonify(error="icao24 invalido"), 400
    icao24 = icao24.lower()
    live = current_app.store.get(icao24) or {}
    callsign = (live.get("cs") or request.args.get("callsign", "")).strip().upper()
    static = current_app.static
    row = static.aircraft(icao24) or {}
    return jsonify(
        aircraft={
            "registration": live.get("reg") or row.get("reg"),
            "type_code": live.get("ty") or row.get("type"),
            "description": row.get("description"),
            "owner": row.get("owner"),
            "year": row.get("year"),
        },
        airline=static.airline(callsign),
        route=static.route(callsign, live.get("lat"), live.get("lon")) if callsign else None,
        military=bool(live.get("mil")),
    )


@bp.route("/api/photo/<icao24>")
def photo(icao24):
    if not ICAO24.fullmatch(icao24):
        return jsonify(error="icao24 invalido"), 400
    cache_dir = os.path.join(current_app.config["DATA_DIR"], "cache", "photos")
    return jsonify(photo=media.photo_for(icao24.lower(), cache_dir))


@bp.route("/api/reference")
def reference():
    """Presion en superficie bajo un punto: sirve para calcular la altura sobre el terreno de un avion."""
    lat, lon = request.args.get("lat", type=float), request.args.get("lon", type=float)
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify(error="lat y lon requeridos"), 400
    return jsonify(surface_hpa=media.surface_pressure_hpa(lat, lon))


@bp.route("/api/track/<icao24>")
def track(icao24):
    until = request.args.get("until", type=int)
    return jsonify(current_app.db.track(icao24.lower(), until=until))


# --- busqueda y aeropuertos ---

@bp.route("/api/search")
def search():
    q = request.args.get("q", "").strip().lower()
    if len(q) < 2:
        return jsonify(flights=[], airports=[])
    found = {}
    for f in current_app.store.flights.values():
        if q in (f.get("cs") or "").lower() or q in f["id"] or q in (f.get("reg") or "").lower():
            found[f["id"]] = public(f)
        if len(found) >= 8:
            break
    for f in current_app.db.recent_matches(q, 8):
        found.setdefault(f["id"], f)
    return jsonify(flights=list(found.values())[:8], airports=current_app.static.search_airports(q))


@bp.route("/api/airports")
def airports():
    bbox, error = parse_bbox()
    if error:
        return error
    zoom = request.args.get("z", 6, type=float)
    max_rank = 0 if zoom < 7 else 1 if zoom < 9 else 2
    return jsonify(current_app.static.airports_in_bbox(bbox, max_rank))


@bp.route("/api/airport/<code>")
def airport(code):
    static, store = current_app.static, current_app.store
    ap = static.airport(code)
    if not ap:
        return jsonify(error="Aeropuerto no encontrado"), 404
    codes = {ap["icao"], ap["ident"], ap["iata"]} - {None}
    d = 1.0  # grados alrededor del aeropuerto para asegurar datos frescos
    store.touch(cells_for_bbox((ap["lat"] - d, ap["lon"] - d, ap["lat"] + d, ap["lon"] + d)))
    nearby = []
    for f in store.flights.values():
        dist = haversine_km(ap["lat"], ap["lon"], f["lat"], f["lon"])
        if dist <= 100:
            nearby.append((dist, f))
    out = {"arriving": [], "departing": [], "ground": 0, "airborne_near": 0}
    for dist, f in sorted(nearby, key=lambda x: x[0]):
        item = {"id": f["id"], "cs": f.get("cs"), "alt": f.get("alt"), "spd": f.get("spd"), "dist_km": round(dist, 1)}
        route = static.route_codes(f["cs"], f["lat"], f["lon"]) if f.get("cs") else None
        if f.get("gnd") and dist < 5:
            out["ground"] += 1
        elif dist < 40:
            out["airborne_near"] += 1
        if route and route[1] in codes and not f.get("gnd"):
            out["arriving"].append(item)
        elif route and route[0] in codes and not f.get("gnd"):
            out["departing"].append(item)
    out["arriving"], out["departing"] = out["arriving"][:15], out["departing"][:15]
    return jsonify(airport=ap, weather=media.weather_at(ap["lat"], ap["lon"]), **out)


# --- historial ---

@bp.route("/api/replay/range")
def replay_range():
    return require_db() or jsonify(current_app.db.replay_range())


@bp.route("/api/replay")
def replay():
    unavailable = require_db()
    if unavailable:
        return unavailable
    bbox, error = parse_bbox()
    if error:
        return error
    t = request.args.get("t", type=int)
    if t is None:
        return jsonify(error="t requerido"), 400
    return jsonify(current_app.db.replay_at(bbox, t))


@bp.route("/api/stats")
def stats():
    unavailable = require_db()
    if unavailable:
        return unavailable
    hours = max(1, min(request.args.get("hours", 24, type=int), current_app.config["RETENTION_DAYS"] * 24))
    data = current_app.db.stats(hours)
    for row in data["airlines"]:
        info = current_app.static.airline(row["airline"] + "0")
        row["name"] = info["name"] if info else None
    return jsonify(hours=hours, **data)


# --- seguimiento y alertas ---

@bp.route("/api/watchlist", methods=["GET", "POST"])
def watchlist():
    unavailable = require_db()
    if unavailable:
        return unavailable
    if request.method == "GET":
        return jsonify(current_app.db.watchlist())
    denied = require_admin()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    kind, value = body.get("kind"), str(body.get("value", "")).strip()
    if kind not in ("callsign", "icao24", "registration", "squawk") or not WATCH_VALUE.fullmatch(value):
        return jsonify(error="kind o value invalido"), 400
    if kind == "squawk" and value in EMERGENCY_SQUAWKS:
        return jsonify(error="Los squawk de emergencia ya se vigilan siempre"), 400
    item = current_app.db.add_watch(kind, value.upper(), str(body.get("label") or "")[:60] or None)
    current_app.alerts.reload_watchlist()
    return jsonify(item), 201


@bp.route("/api/watchlist/<int:watch_id>", methods=["DELETE"])
def watchlist_delete(watch_id):
    unavailable = require_db() or require_admin()
    if unavailable:
        return unavailable
    current_app.db.delete_watch(watch_id)
    current_app.alerts.reload_watchlist()
    return "", 204


@bp.route("/api/alerts")
def alerts():
    return jsonify(current_app.db.alerts() if current_app.db.enabled else current_app.store.events[::-1])
