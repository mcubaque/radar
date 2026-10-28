import logging

import psycopg

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    id BIGSERIAL PRIMARY KEY,
    icao24 TEXT NOT NULL,
    callsign TEXT,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    altitude DOUBLE PRECISION,
    velocity DOUBLE PRECISION,
    heading DOUBLE PRECISION,
    on_ground BOOLEAN,
    time_position BIGINT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (icao24, time_position)
);
CREATE INDEX IF NOT EXISTS positions_icao_time ON positions (icao24, recorded_at DESC);
"""

INSERT = """
INSERT INTO positions (icao24, callsign, latitude, longitude, altitude, velocity, heading, on_ground, time_position)
VALUES (%(icao24)s, %(callsign)s, %(latitude)s, %(longitude)s, %(altitude)s, %(velocity)s, %(heading)s, %(on_ground)s, %(time_position)s)
ON CONFLICT (icao24, time_position) DO NOTHING
"""

SEARCH_KEYS = ("icao24", "callsign", "latitude", "longitude", "altitude", "velocity", "heading", "on_ground")


class Database:
    """Acceso opcional a Postgres: si falla, la app sigue funcionando sin historial."""

    def __init__(self, url):
        self.url = url
        self.enabled = False

    def _connect(self):
        return psycopg.connect(self.url, connect_timeout=5)

    def init(self):
        if not self.url:
            log.warning("DATABASE_URL vacio: historial desactivado")
            return
        try:
            with self._connect() as conn:
                conn.execute(SCHEMA)
            self.enabled = True
        except psycopg.Error as e:
            log.warning("Postgres no disponible, historial desactivado: %s", e)

    def save(self, flights):
        if not self.enabled or not flights:
            return
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.executemany(INSERT, flights)
        except psycopg.Error as e:
            log.warning("No se pudo guardar en Postgres: %s", e)

    def track(self, icao24, hours=6):
        if not self.enabled:
            return []
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT latitude, longitude FROM positions "
                    "WHERE icao24 = %s AND recorded_at > now() - make_interval(hours => %s) "
                    "ORDER BY time_position",
                    (icao24, hours),
                ).fetchall()
            return [list(r) for r in rows]
        except psycopg.Error as e:
            log.warning("Error leyendo trayectoria: %s", e)
            return []

    def search(self, q, limit=10):
        if not self.enabled:
            return []
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT DISTINCT ON (icao24) icao24, callsign, latitude, longitude, altitude, velocity, heading, on_ground "
                    "FROM positions WHERE (callsign ILIKE %s OR icao24 ILIKE %s) "
                    "AND recorded_at > now() - interval '1 hour' "
                    "ORDER BY icao24, recorded_at DESC LIMIT %s",
                    (f"%{q}%", f"%{q}%", limit),
                ).fetchall()
            return [dict(zip(SEARCH_KEYS, r)) for r in rows]
        except psycopg.Error as e:
            log.warning("Error en busqueda: %s", e)
            return []
