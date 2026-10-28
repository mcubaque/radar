"""Informacion aeronautica gratuita: METAR/TAF y SIGMET (aviationweather.gov), viento en altura (Open-Meteo)."""
import logging
import threading
import time

import requests

log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "SkyMonitor/1.0 (proyecto personal; https://github.com/mcubaque/radar)"}
AWC = "https://aviationweather.gov/api/data"
METAR_TTL = 300
SIGMET_TTL = 300
WIND_TTL = 900
RETRY = 60  # tras un fallo, espera antes de volver a preguntar
PRESSURE_LEVELS = (1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150)

_cache = {}
_lock = threading.Lock()


def _cached(key, ttl, load):
    """Resultado de `load()` guardado `ttl` s; un fallo (None) solo se recuerda `RETRY` s."""
    with _lock:
        hit = _cache.get(key)
    if hit and time.time() - hit[0] < (ttl if hit[1] is not None else RETRY):
        return hit[1]
    try:
        value = load()
    except (requests.RequestException, ValueError, KeyError):
        log.warning("Consulta fallida: %s", key)
        value = None
    with _lock:
        _cache[key] = (time.time(), value)
    return value


def _get(url, **params):
    r = requests.get(url, params=params, headers=HEADERS, timeout=8)
    r.raise_for_status()
    return r.json() if r.content else []


def metar(icao):
    """Ultimo METAR decodificado de un aeropuerto, o None si no hay estacion."""
    icao = icao.upper()

    def load():
        rows = _get(f"{AWC}/metar", ids=icao, format="json")
        if not rows:
            return None
        m = rows[0]
        keys = ("rawOb", "obsTime", "temp", "dewp", "wdir", "wspd", "wgst", "visib", "altim", "wxString", "clouds",
                "fltCat")
        return {k: m.get(k) for k in keys}

    return _cached(("metar", icao), METAR_TTL, load)


def taf(icao):
    icao = icao.upper()

    def load():
        rows = _get(f"{AWC}/taf", ids=icao, format="json")
        return {"raw": rows[0].get("rawTAF"), "valid_to": rows[0].get("validTimeTo")} if rows else None

    return _cached(("taf", icao), METAR_TTL, load)


def _polygons(coords):
    """Poligonos GeoJSON de las coordenadas de un SIGMET: una lista de puntos o varias areas (lista de listas)."""
    if coords and isinstance(coords[0], list):
        areas = coords
    else:
        areas = [coords or []]
    out = []
    for area in areas:
        ring = [[c["lon"], c["lat"]] for c in area if isinstance(c, dict) and "lon" in c and "lat" in c]
        if len(ring) < 3:
            continue
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        out.append([ring])
    return out


def sigmets():
    """SIGMET vigentes (tormentas, turbulencia, hielo, ceniza...) como GeoJSON FeatureCollection."""

    def load():
        now = time.time()
        features = []
        for s in _get(f"{AWC}/isigmet", format="json"):
            features.append(("isigmet", s["hazard"], s.get("top"), s.get("base"), s.get("validTimeTo"),
                             s.get("firName"), s.get("coords"), s.get("rawSigmet") or ""))
        for s in _get(f"{AWC}/airsigmet", format="json"):
            features.append(("airsigmet", s.get("hazard"), s.get("altitudeHi1"), s.get("altitudeLow1"),
                             s.get("validTimeTo"), s.get("airSigmetType"), s.get("coords"),
                             s.get("rawAirSigmet") or ""))
        out = []
        for kind, hazard, top, base, valid_to, name, coords, raw in features:
            polygons = _polygons(coords)
            if not polygons or (valid_to and valid_to < now):
                continue
            geometry = {"type": "MultiPolygon", "coordinates": polygons}
            out.append({"type": "Feature", "geometry": geometry, "properties": {
                "hazard": hazard or "?", "top_ft": top, "base_ft": base, "valid_to": valid_to,
                "name": name, "source": kind, "text": raw[:600],
            }})
        return {"type": "FeatureCollection", "features": out}

    return _cached(("sigmets",), SIGMET_TTL, load)


def pressure_at(alt_m):
    """Presion (hPa) a una altitud, atmosfera estandar."""
    return 1013.25 * (1 - max(alt_m, 0) / 44330.77) ** (1 / 0.190263)


def pressure_level(alt_m):
    p = pressure_at(alt_m)
    return min(PRESSURE_LEVELS, key=lambda level: abs(level - p))


def wind_aloft(lat, lon, alt_m):
    """Viento (direccion de la que sopla en grados, velocidad en kt) en el nivel de presion mas cercano a `alt_m`."""
    level = pressure_level(alt_m)
    key = ("wind", round(lat, 1), round(lon, 1), level)

    def load():
        data = _get("https://api.open-meteo.com/v1/forecast", latitude=lat, longitude=lon, wind_speed_unit="kn",
                    current=f"wind_speed_{level}hPa,wind_direction_{level}hPa")["current"]
        speed, direction = data[f"wind_speed_{level}hPa"], data[f"wind_direction_{level}hPa"]
        if speed is None or direction is None:
            return None
        return {"level_hpa": level, "dir": direction, "kt": speed}

    return _cached(key, WIND_TTL, load)

