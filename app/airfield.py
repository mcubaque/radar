"""Pista en uso de un aeropuerto, deducida de como vuelan los aviones que estan cerca de ella."""
import math

MAX_DIST_KM = 15  # a mas distancia del centro de la pista un avion no cuenta
MAX_CROSS_KM = 2.5  # separacion maxima respecto al eje de la pista
MAX_HEADING_DIFF = 25
MAX_AGL_M = 1500
MIN_VOTES = 2


def _diff(a, b):
    return abs((a - b + 180) % 360 - 180)


def runway_in_use(runways, flights, elevation_m):
    """Cabecera (p. ej. '31L') con mas aviones alineados llegando o saliendo, o None si no hay evidencia suficiente."""
    votes = {}
    for rw in runways:
        for ident, hdg in ((rw["le_ident"], rw["le_hdg"]), (rw["he_ident"], rw["he_hdg"])):
            count = 0
            for f in flights:
                if f.get("hdg") is None or _diff(f["hdg"], hdg) > MAX_HEADING_DIFF:
                    continue
                if not f.get("gnd") and (f.get("alt") is None or f["alt"] - elevation_m > MAX_AGL_M):
                    continue
                if f.get("gnd") and (f.get("spd") or 0) < 15:  # rodando por calles o parado: no indica la pista
                    continue
                dy = (f["lat"] - rw["lat"]) * 111.32
                dx = (f["lon"] - rw["lon"]) * 111.32 * math.cos(math.radians(rw["lat"]))
                h = math.radians(hdg)
                cross = abs(dx * math.cos(h) - dy * math.sin(h))
                if math.hypot(dx, dy) <= MAX_DIST_KM and cross <= MAX_CROSS_KM:
                    count += 1
            votes[ident] = count
    best = max(votes, key=votes.get, default=None)
    return best if best and votes[best] >= MIN_VOTES else None
