"""Blueprint compartido y utilidades comunes de las rutas HTTP."""
import hmac
import re

from flask import Blueprint, current_app, jsonify, request

from app.flight import cells_for_bbox

bp = Blueprint("main", __name__)

ICAO24 = re.compile(r"[0-9a-fA-F]{6}")


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


def is_admin():
    token = current_app.config["ADMIN_TOKEN"]
    return not token or hmac.compare_digest(request.headers.get("X-Admin-Token", ""), token)


def require_admin():
    return None if is_admin() else (jsonify(error="No autorizado"), 401)
