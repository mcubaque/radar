from flask import Blueprint, current_app, jsonify, render_template, request

from app.opensky import OpenSkyError

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/api/flights")
def flights():
    try:
        bbox = tuple(float(request.args[k]) for k in ("lamin", "lomin", "lamax", "lomax"))
    except (KeyError, ValueError):
        return jsonify(error="Parametros lamin, lomin, lamax, lomax requeridos"), 400
    if bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
        return jsonify(error="bbox invalido"), 400
    try:
        data = current_app.opensky.get_flights(bbox)
    except OpenSkyError as e:
        return jsonify(error=str(e)), e.status
    # El guardado lo hace el recorder en segundo plano; aqui solo se lee
    return jsonify(data)


@bp.route("/api/track/<icao24>")
def track(icao24):
    return jsonify(current_app.db.track(icao24.lower()))


@bp.route("/api/search")
def search():
    q = request.args.get("q", "").strip().lower()
    if len(q) < 2:
        return jsonify([])
    found = {f["icao24"]: f for f in current_app.db.search(q)}
    for f in current_app.opensky.cached_flights():
        if q in f["callsign"].lower() or q in f["icao24"]:
            found[f["icao24"]] = f
    return jsonify(list(found.values())[:10])
