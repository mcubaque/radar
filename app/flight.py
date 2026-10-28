"""Formato interno de un vuelo y geometria de celdas.

Un vuelo es un dict con claves cortas y unidades SI (altitud en m, velocidades en m/s):
id, cs (callsign), reg, ty (tipo OACI), cat (categoria ADS-B), lat, lon, alt, spd, hdg, vr,
gnd (en tierra), sq (squawk), em (emergencia), mil (militar), int (aeronave de interes), ts (epoch de la posicion).
Las claves con valor None se omiten.
"""
import math
import time

FT = 0.3048
KT = 0.514444
FPM = 0.00508
EMERGENCY_SQUAWKS = {"7500", "7600", "7700"}
MAX_POSITION_AGE = 60  # segundos; mas viejo se descarta

# Categoria de OpenSky (indice 17 con extended=1) -> categoria ADS-B que usa el resto de la app
OPENSKY_CATEGORY = {2: "A1", 3: "A2", 4: "A3", 5: "A4", 6: "A5", 7: "A6", 8: "A7"}

CELL_DEG = 5
MAX_RADIUS_NM = 250


def _clean(d):
    return {k: v for k, v in d.items() if v is not None}


def normalize_readsb(ac, now=None):
    """Convierte un avion de aircraft.json (readsb, adsb.lol, adsb.fi) al formato interno."""
    now = now or time.time()
    lat, lon = ac.get("lat"), ac.get("lon")
    if lat is None or lon is None or not ac.get("hex"):
        return None
    age = ac.get("seen_pos", 0)
    if age > MAX_POSITION_AGE:
        return None
    alt = ac.get("alt_baro")
    on_ground = alt == "ground"
    if on_ground or alt is None:
        alt = ac.get("alt_geom")
    squawk = ac.get("squawk")
    emergency = ac.get("emergency") not in (None, "none") or squawk in EMERGENCY_SQUAWKS
    return _clean({
        "id": ac["hex"].lower().lstrip("~"),
        "cs": (ac.get("flight") or "").strip() or None,
        "reg": ac.get("r"),
        "ty": ac.get("t"),
        "cat": ac.get("category"),
        "lat": round(lat, 5),
        "lon": round(lon, 5),
        "alt": round(alt * FT) if isinstance(alt, (int, float)) and not on_ground else None,
        "spd": round(ac["gs"] * KT, 1) if isinstance(ac.get("gs"), (int, float)) else None,
        "hdg": round(ac["track"]) if isinstance(ac.get("track"), (int, float)) else None,
        "vr": round(ac["baro_rate"] * FPM, 1) if isinstance(ac.get("baro_rate"), (int, float)) else None,
        "gnd": 1 if on_ground else None,
        "sq": squawk,
        "em": 1 if emergency else None,
        "mil": 1 if (ac.get("dbFlags") or 0) & 1 else None,
        "int": 1 if (ac.get("dbFlags") or 0) & 2 else None,
        "ts": round(now - age),
    })


def normalize_opensky(s, now=None):
    """Convierte un 'state vector' de OpenSky al formato interno."""
    now = now or time.time()
    lon, lat = s[5], s[6]
    if lat is None or lon is None or now - (s[3] or now) > MAX_POSITION_AGE:
        return None
    alt = s[7] if s[7] is not None else s[13]
    squawk = s[14] if len(s) > 14 else None
    return _clean({
        "id": s[0],
        "cs": (s[1] or "").strip() or None,
        "cat": OPENSKY_CATEGORY.get(s[17]) if len(s) > 17 else None,
        "lat": round(lat, 5),
        "lon": round(lon, 5),
        "alt": round(alt) if alt is not None and not s[8] else None,
        "spd": s[9],
        "hdg": round(s[10]) if s[10] is not None else None,
        "vr": s[11],
        "gnd": 1 if s[8] else None,
        "sq": squawk,
        "em": 1 if squawk in EMERGENCY_SQUAWKS else None,
        "ts": s[3] or round(now),
    })


def mark_grounded(f):
    """Pasa un vuelo a 'en tierra': sin altitud ni velocidad vertical (la barometrica en pista no significa nada)."""
    f["gnd"] = 1
    f.pop("alt", None)
    f.pop("vr", None)


# --- geometria ---

def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))


def cell_bounds(cell):
    i, j = cell
    return i * CELL_DEG, j * CELL_DEG, (i + 1) * CELL_DEG, (j + 1) * CELL_DEG


def cell_center_radius_nm(cell):
    lamin, lomin, lamax, lomax = cell_bounds(cell)
    clat, clon = (lamin + lamax) / 2, (lomin + lomax) / 2
    radius_km = max(haversine_km(clat, clon, la, lo) for la in (lamin, lamax) for lo in (lomin, lomax))
    return clat, clon, min(MAX_RADIUS_NM, math.ceil(radius_km / 1.852 * 1.02))


def cells_for_bbox(bbox):
    """Celdas de CELL_DEG grados que cubren (lamin, lomin, lamax, lomax)."""
    lamin, lomin, lamax, lomax = bbox

    def span(low, high):  # el borde superior es exclusivo: un limite exacto en 45 no incluye la celda 45-50
        first = math.floor(low / CELL_DEG)
        return range(first, max(first, math.ceil(high / CELL_DEG) - 1) + 1)

    return [(i, j) for i in span(lamin, lamax) for j in span(lomin, lomax)]


def in_bbox(f, bbox):
    return bbox[0] <= f["lat"] <= bbox[2] and bbox[1] <= f["lon"] <= bbox[3]
