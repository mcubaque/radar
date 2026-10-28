"""Datos de referencia (aeronaves, aeropuertos, rutas, aerolineas) en un SQLite local.

Se descargan una vez desde fuentes publicas y se consultan sin llamar a ninguna API.
"""
import csv
import gzip
import logging
import math
import os
import re
import sqlite3
import threading

import requests

from app.flight import haversine_km

log = logging.getLogger(__name__)

SOURCES = {
    "aircraft.csv.gz": "https://github.com/wiedehopf/tar1090-db/raw/csv/aircraft.csv.gz",
    "airports.csv": "https://davidmegginson.github.io/ourairports-data/airports.csv",
    "routes.csv.gz": "https://vrs-standing-data.adsb.lol/routes.csv.gz",
    "airport-frequencies.csv": "https://davidmegginson.github.io/ourairports-data/airport-frequencies.csv",
    "runways.csv": "https://davidmegginson.github.io/ourairports-data/runways.csv",
    "airlines.dat": "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat",
}
ROUTE_TOLERANCE_KM = 80  # margen fijo y proporcional al largo del tramo para desvios del avion respecto al arco directo
ROUTE_TOLERANCE_RATIO = 0.12
LEADING_ZEROS = re.compile(r"^([A-Z]{2,3})0+(\d)")
RUNWAY_COLUMNS = ("length_ft, width_ft, surface, le_ident, le_hdg, he_ident, he_hdg, lat, lon, "
                  "le_lat, le_lon, he_lat, he_lon")
FREQUENCY_ORDER = ["ATIS", "CLD", "GND", "TWR", "APP", "DEP", "ACC", "CTAF", "UNIC", "RDO"]
AIRPORT_TYPES = {"large_airport": 0, "medium_airport": 1, "small_airport": 2}

SCHEMA = """
CREATE TABLE aircraft (icao24 TEXT PRIMARY KEY, reg TEXT, type TEXT, description TEXT, year TEXT, owner TEXT);
CREATE TABLE airports (ident TEXT PRIMARY KEY, icao TEXT, iata TEXT, name TEXT, city TEXT, country TEXT,
                       type TEXT, rank INTEGER, lat REAL, lon REAL, elevation_ft INTEGER);
CREATE INDEX airports_iata ON airports (iata);
CREATE INDEX airports_lat ON airports (lat);
CREATE TABLE routes (callsign TEXT PRIMARY KEY, airports TEXT);
CREATE TABLE runways (airport TEXT, length_ft INTEGER, width_ft INTEGER, surface TEXT,
                      le_ident TEXT, le_hdg REAL, he_ident TEXT, he_hdg REAL, lat REAL, lon REAL,
                      le_lat REAL, le_lon REAL, he_lat REAL, he_lon REAL);
CREATE INDEX runways_airport ON runways (airport);
CREATE TABLE frequencies (airport TEXT, type TEXT, description TEXT, mhz REAL);
CREATE INDEX frequencies_airport ON frequencies (airport);
CREATE TABLE airlines (icao TEXT PRIMARY KEY, name TEXT, country TEXT);
"""


def _runway_heading(ident, given):
    """Rumbo verdadero de una cabecera: el dato de OurAirports o, si falta, el numero de pista x 10."""
    if given:
        return float(given)
    digits = "".join(c for c in ident if c.isdigit())
    return int(digits) * 10.0 % 360 if digits and len(digits) <= 2 else None


def _runway_row(r):
    """Fila (aeropuerto, largo, superficie, cabeceras, rumbos, centro) de una pista abierta, o None si no sirve."""
    if r["closed"] == "1" or not r["le_ident"] or not r["he_ident"]:
        return None
    ends = [(r["le_latitude_deg"], r["le_longitude_deg"]), (r["he_latitude_deg"], r["he_longitude_deg"])]
    if not all(lat and lon for lat, lon in ends):
        return None
    le_hdg = _runway_heading(r["le_ident"], r["le_heading_degT"])
    he_hdg = _runway_heading(r["he_ident"], r["he_heading_degT"])
    if le_hdg is None or he_hdg is None:
        return None
    lat = (float(ends[0][0]) + float(ends[1][0])) / 2
    lon = (float(ends[0][1]) + float(ends[1][1])) / 2
    return (r["airport_ident"], int(r["length_ft"] or 0), int(r["width_ft"] or 0), r["surface"], r["le_ident"], le_hdg,
            r["he_ident"], he_hdg, lat, lon, float(ends[0][0]), float(ends[0][1]), float(ends[1][0]), float(ends[1][1]))


def build_static_db(raw_dir, out_path):
    """Construye el SQLite a partir de los archivos descargados. Escribe a un temporal y reemplaza."""
    tmp = out_path + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA)

    def open_text(name):
        path = os.path.join(raw_dir, name)
        opener = gzip.open if name.endswith(".gz") else open
        return opener(path, "rt", encoding="utf-8-sig", newline="")

    if os.path.exists(os.path.join(raw_dir, "aircraft.csv.gz")):
        with open_text("aircraft.csv.gz") as f:
            rows = ((r[0].lower(), r[1], r[2], r[4], r[5], r[6]) for r in csv.reader(f, delimiter=";") if len(r) >= 7)
            db.executemany("INSERT OR IGNORE INTO aircraft VALUES (?,?,?,?,?,?)", rows)
    if os.path.exists(os.path.join(raw_dir, "airports.csv")):
        with open_text("airports.csv") as f:
            for r in csv.DictReader(f):
                if r["type"] in AIRPORT_TYPES:
                    db.execute(
                        "INSERT OR IGNORE INTO airports VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (r["ident"], r["icao_code"] or r["ident"], r["iata_code"] or None, r["name"], r["municipality"],
                         r["iso_country"], r["type"], AIRPORT_TYPES[r["type"]], float(r["latitude_deg"]),
                         float(r["longitude_deg"]), int(r["elevation_ft"]) if r["elevation_ft"] else None),
                    )
    if os.path.exists(os.path.join(raw_dir, "runways.csv")):
        with open_text("runways.csv") as f:
            for r in csv.DictReader(f):
                row = _runway_row(r)
                if row:
                    db.execute("INSERT INTO runways VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
    if os.path.exists(os.path.join(raw_dir, "airport-frequencies.csv")):
        with open_text("airport-frequencies.csv") as f:
            db.executemany(
                "INSERT INTO frequencies VALUES (?,?,?,?)",
                ((r["airport_ident"], r["type"], r["description"], float(r["frequency_mhz"]))
                 for r in csv.DictReader(f) if r["frequency_mhz"]),
            )
    if os.path.exists(os.path.join(raw_dir, "routes.csv.gz")):
        with open_text("routes.csv.gz") as f:
            db.executemany(
                "INSERT OR IGNORE INTO routes VALUES (?,?)",
                ((r["Callsign"], r["AirportCodes"]) for r in csv.DictReader(f) if r.get("AirportCodes")),
            )
    if os.path.exists(os.path.join(raw_dir, "airlines.dat")):
        with open_text("airlines.dat") as f:
            for r in csv.reader(f):
                # id, nombre, alias, iata, icao, callsign, pais, activa
                if len(r) >= 8 and len(r[4]) == 3 and r[7] == "Y":
                    db.execute("INSERT OR IGNORE INTO airlines VALUES (?,?,?)", (r[4], r[1], r[6]))
    db.commit()
    db.close()
    os.replace(tmp, out_path)


def download_missing(raw_dir, force=False):
    os.makedirs(raw_dir, exist_ok=True)
    for name, url in SOURCES.items():
        path = os.path.join(raw_dir, name)
        if os.path.exists(path) and not force:
            continue
        log.info("Descargando %s", url)
        with requests.get(url, stream=True, timeout=60, headers={"User-Agent": "SkyMonitor/1.0"}) as r:
            r.raise_for_status()
            with open(path + ".part", "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
        os.replace(path + ".part", path)


class StaticData:
    def __init__(self, data_dir):
        self.raw_dir = os.path.join(data_dir, "static", "raw")
        self.path = os.path.join(data_dir, "static", "static.sqlite")
        self._local = threading.local()
        self.building = False
        self._grid = None  # (lat, lon) en celdas de 0.1 grados -> [(lat, lon, elevacion_m)]
        self._grid_lock = threading.Lock()

    @property
    def ready(self):
        return os.path.exists(self.path)

    def outdated(self):
        """True si el SQLite existe pero se construyo antes de agregar las tablas de pistas y frecuencias."""
        if not self.ready:
            return False
        db = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)  # conexion propia: no impide reemplazar el archivo
        try:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            columns = {r[1] for r in db.execute("PRAGMA table_info(runways)")}
            return not {"runways", "frequencies"} <= tables or "le_lat" not in columns
        finally:
            db.close()

    def runways(self, ident):
        try:
            return self._all(f"SELECT {RUNWAY_COLUMNS} FROM runways WHERE airport = ?", (ident,))
        except sqlite3.OperationalError:  # conexion abierta antes de reconstruir la base: sin pistas hasta reiniciar
            return []

    def runways_near(self, lat, lon, radius_deg=0.35, limit=6):
        """Pistas (con sus extremos) de los aeropuertos cercanos a un punto, para dibujarlas en la vista 3D."""
        bbox = (lat - radius_deg, lon - radius_deg, lat + radius_deg, lon + radius_deg)
        airports = sorted(self.airports_in_bbox(bbox, max_rank=2, limit=60),
                          key=lambda a: haversine_km(lat, lon, a["lat"], a["lon"]))[:limit]
        return [{"ident": a["ident"], "elevation_ft": a["elevation_ft"], "runways": self.runways(a["ident"])}
                for a in airports]

    def frequencies(self, ident, limit=14):
        """Frecuencias de radio del aeropuerto (ATIS, torre, tierra, aproximacion...), las de control primero."""
        try:
            rows = self._all(
                "SELECT type, description, mhz FROM frequencies "
                "WHERE airport = ? AND mhz BETWEEN 100 AND 400", (ident,))
        except sqlite3.OperationalError:  # base anterior a la tabla de frecuencias: vacio hasta reconstruirla
            return []
        rows.sort(key=lambda r: (FREQUENCY_ORDER.index(r["type"]) if r["type"] in FREQUENCY_ORDER else 99, r["mhz"]))
        return rows[:limit]

    def prepare(self, force=False):
        """Descarga y construye si falta. Pensado para correr en un hilo de fondo."""
        if self.ready and not force and not self.outdated():
            return
        self.building = True
        try:
            download_missing(self.raw_dir, force)
            build_static_db(self.raw_dir, self.path)
            log.info("Datos de referencia listos en %s", self.path)
        except PermissionError as e:  # Windows no deja reemplazar un archivo abierto: reconstruir con la app detenida
            log.warning("No se pudo reemplazar la base de referencia (esta en uso), reinicia la app: %s", e)
        except (requests.RequestException, OSError, sqlite3.Error) as e:
            log.warning("No se pudieron preparar los datos de referencia: %s", e)
        finally:
            self.building = False

    def _db(self):
        if not self.ready:
            return None
        db = getattr(self._local, "db", None)
        if db is None:
            db = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, check_same_thread=False)
            db.row_factory = sqlite3.Row
            self._local.db = db
        return db

    def _all(self, sql, params=()):
        db = self._db()
        return [dict(r) for r in db.execute(sql, params)] if db else []

    def _one(self, sql, params=()):
        rows = self._all(sql, params)
        return rows[0] if rows else None

    def aircraft(self, icao24):
        return self._one("SELECT reg, type, description, year, owner FROM aircraft WHERE icao24 = ?", (icao24,))

    def airport(self, code):
        code = code.upper()
        return self._one("SELECT * FROM airports WHERE iata = ? OR icao = ? OR ident = ?", (code, code, code))

    def _airport_grid(self):
        if self._grid is None and self.ready:
            with self._grid_lock:
                if self._grid is None:
                    grid = {}
                    for r in self._all("SELECT lat, lon, elevation_ft FROM airports WHERE elevation_ft IS NOT NULL"):
                        key = (math.floor(r["lat"] * 10), math.floor(r["lon"] * 10))
                        grid.setdefault(key, []).append((r["lat"], r["lon"], r["elevation_ft"] * 0.3048))
                    self._grid = grid
        return self._grid or {}

    def airport_near(self, lat, lon, max_km):
        """(elevacion m, lat, lon) del aeropuerto mas cercano a menos de `max_km`, o None."""
        grid, best = self._airport_grid(), None
        ci, cj = math.floor(lat * 10), math.floor(lon * 10)
        for i in (ci - 1, ci, ci + 1):
            for j in (cj - 1, cj, cj + 1):
                for a_lat, a_lon, elevation in grid.get((i, j), ()):
                    d = haversine_km(lat, lon, a_lat, a_lon)
                    if d <= max_km and (best is None or d < best[0]):
                        best = (d, (elevation, a_lat, a_lon))
        return best[1] if best else None

    def airline(self, callsign):
        if not callsign or len(callsign) < 4 or not callsign[:3].isalpha() or not callsign[3].isdigit():
            return None
        return self._one("SELECT icao, name, country FROM airlines WHERE icao = ?", (callsign[:3].upper(),))

    def route_codes(self, callsign, lat=None, lon=None):
        """(origen, destino) del tramo que el avion esta volando, o None si no se puede asegurar.

        La tabla de rutas es por callsign y un numero de vuelo cambia de ruta segun el dia, asi que con una
        posicion se comprueba que el avion este sobre el tramo (con margen para desvios); si no, se descarta.
        Sin posicion solo se acepta una ruta de un unico tramo, sin validar.
        """
        row = None
        if callsign:
            # los aviones transmiten AVA054 y la tabla guarda AVA54: se prueba tambien sin ceros a la izquierda
            call = callsign.upper()
            for key in dict.fromkeys((call, LEADING_ZEROS.sub(lambda m: m[1] + m[2], call))):
                row = self._one("SELECT airports FROM routes WHERE callsign = ?", (key,))
                if row:
                    break
        parts = row["airports"].split("-") if row else []
        if len(parts) < 2:
            return None
        if lat is None:
            return tuple(parts) if len(parts) == 2 else None
        airports = {code: self.airport(code) for code in set(parts)}
        best = None
        for a, b in zip(parts, parts[1:], strict=False):
            pa, pb = airports[a], airports[b]
            if not pa or not pb:
                continue
            length = haversine_km(pa["lat"], pa["lon"], pb["lat"], pb["lon"])
            # desvio respecto al tramo: ~0 si el avion va sobre la ruta a->b
            via = haversine_km(pa["lat"], pa["lon"], lat, lon) + haversine_km(lat, lon, pb["lat"], pb["lon"])
            detour = via - length
            if detour <= ROUTE_TOLERANCE_KM + ROUTE_TOLERANCE_RATIO * length and (best is None or detour < best[0]):
                best = (detour, a, b)
        return best[1:] if best else None

    def route(self, callsign, lat=None, lon=None):
        codes = self.route_codes(callsign, lat, lon)
        if not codes:
            return None
        origin, destination = (self.airport(code) or {"icao": code} for code in codes)
        return {"origin": origin, "destination": destination}

    def search_airports(self, q, limit=6):
        like = f"%{q.lower()}%"
        return self._all(
            "SELECT ident, icao, iata, name, city, country, lat, lon FROM airports "
            "WHERE iata = ? OR icao = ? OR lower(name) LIKE ? OR lower(city) LIKE ? "
            "ORDER BY (iata = ? OR icao = ?) DESC, rank LIMIT ?",
            (q.upper(), q.upper(), like, like, q.upper(), q.upper(), limit),
        )

    def airports_in_bbox(self, bbox, max_rank, limit=300):
        return self._all(
            "SELECT ident, icao, iata, name, lat, lon, rank, elevation_ft FROM airports "
            "WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ? AND rank <= ? AND (iata IS NOT NULL OR rank = 0) "
            "ORDER BY rank LIMIT ?",
            (bbox[0], bbox[2], bbox[1], bbox[3], max_rank, limit),
        )

