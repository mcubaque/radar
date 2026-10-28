"""Datos de referencia (aeronaves, aeropuertos, rutas, aerolineas) en un SQLite local.

Se descargan una vez desde fuentes publicas y se consultan sin llamar a ninguna API.
"""
import csv
import gzip
import logging
import math
import os
import sqlite3
import threading

import requests

from app.flight import haversine_km

log = logging.getLogger(__name__)

SOURCES = {
    "aircraft.csv.gz": "https://github.com/wiedehopf/tar1090-db/raw/csv/aircraft.csv.gz",
    "airports.csv": "https://davidmegginson.github.io/ourairports-data/airports.csv",
    "routes.csv.gz": "https://vrs-standing-data.adsb.lol/routes.csv.gz",
    "airlines.dat": "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat",
}
ROUTE_TOLERANCE_KM = 80  # margen fijo y proporcional al largo del tramo para desvios del avion respecto al arco directo
ROUTE_TOLERANCE_RATIO = 0.12
AIRPORT_TYPES = {"large_airport": 0, "medium_airport": 1, "small_airport": 2}

SCHEMA = """
CREATE TABLE aircraft (icao24 TEXT PRIMARY KEY, reg TEXT, type TEXT, description TEXT, year TEXT, owner TEXT);
CREATE TABLE airports (ident TEXT PRIMARY KEY, icao TEXT, iata TEXT, name TEXT, city TEXT, country TEXT,
                       type TEXT, rank INTEGER, lat REAL, lon REAL, elevation_ft INTEGER);
CREATE INDEX airports_iata ON airports (iata);
CREATE INDEX airports_lat ON airports (lat);
CREATE TABLE routes (callsign TEXT PRIMARY KEY, airports TEXT);
CREATE TABLE airlines (icao TEXT PRIMARY KEY, name TEXT, country TEXT);
"""


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

    def prepare(self, force=False):
        """Descarga y construye si falta. Pensado para correr en un hilo de fondo."""
        if self.ready and not force:
            return
        self.building = True
        try:
            download_missing(self.raw_dir, force)
            build_static_db(self.raw_dir, self.path)
            log.info("Datos de referencia listos en %s", self.path)
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
        row = self._one("SELECT airports FROM routes WHERE callsign = ?", (callsign.upper(),)) if callsign else None
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
            "SELECT ident, icao, iata, name, lat, lon, rank FROM airports "
            "WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ? AND rank <= ? AND (iata IS NOT NULL OR rank = 0) "
            "ORDER BY rank LIMIT ?",
            (bbox[0], bbox[2], bbox[1], bbox[3], max_rank, limit),
        )

