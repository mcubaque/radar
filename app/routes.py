"""Rutas de la pagina, el estado del servidor, los vuelos en vivo y el detalle de un vuelo."""
import json
import os
import time

from flask import Response, current_app, jsonify, render_template, request, send_from_directory, stream_with_context

from app import media
from app.extensions import limiter
from app.flight import cells_for_bbox
from app.web import ICAO24, bp, parse_bbox, public

KEEPALIVE_S = 15


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


@bp.route("/api/status")
def status():
    """Fuente de datos activa, creditos restantes de OpenSky y ritmo de actualizacion."""
    store = current_app.store
    return jsonify(**store.meta, ttl=round(store.cell_ttl * store.ttl_factor, 1), streams=current_app.streams[0])


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
    streams = current_app.streams
    private = bool(current_app.config["ADMIN_TOKEN"])  # con token, las alertas de seguimiento no salen por el stream
    with streams[1]:
        if streams[0] >= current_app.config["MAX_STREAMS"]:
            return jsonify(error="Demasiados espectadores conectados, intenta en un momento"), 503
        streams[0] += 1

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
            yield sse("flights", {"full": first, "flights": changed, "gone": gone, "errors": store.errors(cells),
                                  "meta": store.meta})
            for event in store.events_after(last_event):
                if not (private and event["kind"] == "watch"):
                    yield sse("alert", event)
                last_event = event["id"]
            sent, last_version, first = ids, version, False

    response = Response(stream_with_context(generate()), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })

    def release():
        with streams[1]:
            streams[0] -= 1

    response.call_on_close(release)  # corre aunque el cliente se vaya antes de la primera lectura
    return response


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
    icao24 = icao24.lower()
    recorded = current_app.db.track(icao24, until=until)
    if until is not None:
        return jsonify(recorded)
    if len(recorded) < 2:
        recorded = current_app.store.track(icao24)  # sin historial grabado: las posiciones recientes en memoria
    # lo observado aqui solo cubre desde que se vio el vuelo; la fuente aporta el recorrido desde el despegue
    full = current_app.chain.track(icao24)
    last = full[-1][3] if full else 0
    return jsonify(full + [p for p in recorded if p[3] > last])


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
