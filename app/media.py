"""Fotos de aeronaves (Planespotters) y clima (Open-Meteo), con cache para no repetir peticiones."""
import json
import logging
import os
import time

import requests

log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "SkyMonitor/1.0 (proyecto personal; https://github.com/mcubaque/radar)"}
PHOTO_TTL = 7 * 86400
WEATHER_TTL = 600
WEATHER_RETRY = 60  # tras un fallo, espera antes de volver a preguntar
_weather_cache = {}


def photo_for(icao24, cache_dir):
    """Foto de la aeronave o None. Se guarda en disco, incluso el 'no hay foto', por 7 dias."""
    path = os.path.join(cache_dir, f"{icao24}.json")
    try:
        if time.time() - os.path.getmtime(path) < PHOTO_TTL:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except (OSError, ValueError):
        pass
    photo = None
    try:
        r = requests.get(f"https://api.planespotters.net/pub/photos/hex/{icao24}", headers=HEADERS, timeout=6)
        if r.status_code != 200:
            return None  # error temporal: no se guarda en cache
        first = (r.json().get("photos") or [None])[0]
        if first:
            photo = {
                "url": first["thumbnail_large"]["src"],
                "photographer": first.get("photographer"),
                "link": first.get("link"),
            }
    except (requests.RequestException, ValueError, KeyError):
        return None
    os.makedirs(cache_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(photo, f)
    return photo


def weather_at(lat, lon):
    key = (round(lat, 1), round(lon, 1))
    cached = _weather_cache.get(key)
    if cached and time.time() - cached[0] < (WEATHER_TTL if cached[1] else WEATHER_RETRY):
        return cached[1]
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", timeout=5, params={
            "latitude": lat, "longitude": lon, "wind_speed_unit": "kn",
            "current": "temperature_2m,wind_speed_10m,wind_direction_10m,weather_code,visibility,surface_pressure",
        })
        r.raise_for_status()
        current = r.json().get("current")
    except (requests.RequestException, ValueError):
        current = None  # tambien se recuerda el fallo un rato, para no esperar 5 s en cada consulta
    _weather_cache[key] = (time.time(), current)
    return current


def surface_pressure_hpa(lat, lon):
    current = weather_at(lat, lon)
    return current.get("surface_pressure") if current else None
