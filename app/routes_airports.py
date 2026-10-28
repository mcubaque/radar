"""Rutas aeronauticas: aeropuertos, pistas, METAR/TAF, SIGMET y viento en altura."""
from flask import current_app, jsonify, request

from app import airfield, aviation, media
from app.flight import cells_for_bbox, haversine_km
from app.web import bp, parse_bbox


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
    runways = static.runways(ap["ident"])
    near = [f for f in store.flights.values() if haversine_km(ap["lat"], ap["lon"], f["lat"], f["lon"]) <= 20]
    elevation = (ap.get("elevation_ft") or 0) * 0.3048
    return jsonify(
        airport=ap, weather=media.weather_at(ap["lat"], ap["lon"]), metar=aviation.metar(ap["icao"]),
        taf=aviation.taf(ap["icao"]), runways=runways, runway_in_use=airfield.runway_in_use(runways, near, elevation),
        frequencies=static.frequencies(ap["ident"]), **out)


@bp.route("/api/runways")
def runways_near():
    """Pistas de los aeropuertos cercanos a un punto (la vista 3D las dibuja sobre el terreno)."""
    lat, lon = request.args.get("lat", type=float), request.args.get("lon", type=float)
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify(error="lat y lon requeridos"), 400
    return jsonify(current_app.static.runways_near(lat, lon))


@bp.route("/api/sigmets")
def sigmets():
    return jsonify(aviation.sigmets() or {"type": "FeatureCollection", "features": []})


@bp.route("/api/wind")
def wind():
    """Viento en el nivel de presion que corresponde a la altitud de un avion."""
    lat, lon, alt = (request.args.get(k, type=float) for k in ("lat", "lon", "alt"))
    if None in (lat, lon, alt) or not (-90 <= lat <= 90 and -180 <= lon <= 180 and 0 <= alt <= 20000):
        return jsonify(error="lat, lon y alt (m) requeridos"), 400
    return jsonify(wind=aviation.wind_aloft(lat, lon, alt))
