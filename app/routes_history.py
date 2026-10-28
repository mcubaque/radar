"""Rutas del historial grabado: reproduccion, estadisticas, lista de seguimiento y alertas."""
import re

from flask import current_app, jsonify, request

from app.flight import EMERGENCY_SQUAWKS
from app.web import bp, is_admin, parse_bbox, require_admin, require_db

WATCH_VALUE = re.compile(r"[A-Za-z0-9 ]{2,20}")


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
    denied = require_admin()  # con ADMIN_TOKEN la lista de seguimiento es privada tambien para leerla
    if denied:
        return denied
    if request.method == "GET":
        return jsonify(current_app.db.watchlist())
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
    events = current_app.db.alerts() if current_app.db.enabled else current_app.store.events[::-1]
    if not is_admin():  # sin token solo se ven las emergencias, que son publicas por naturaleza
        events = [e for e in events if e["kind"] == "emergency"]
    return jsonify(events)
