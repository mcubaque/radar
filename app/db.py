"""Acceso a PostgreSQL. Todo es opcional: sin base de datos la app funciona sin historial."""
import logging
import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

log = logging.getLogger(__name__)

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "migrations")

INSERT = """
INSERT INTO positions (icao24, callsign, latitude, longitude, altitude, velocity, heading, on_ground,
                       time_position, vertical_rate, squawk, type_code, registration)
VALUES (%(id)s, %(cs)s, %(lat)s, %(lon)s, %(alt)s, %(spd)s, %(hdg)s, %(gnd)s,
        %(ts)s, %(vr)s, %(sq)s, %(ty)s, %(reg)s)
ON CONFLICT (icao24, time_position) DO NOTHING
"""

REPLAY_COLUMNS = (
    "icao24 AS id, callsign AS cs, latitude AS lat, longitude AS lon, altitude AS alt, velocity AS spd, "
    "heading AS hdg, vertical_rate AS vr, on_ground AS gnd, squawk AS sq, registration AS reg, "
    "type_code AS ty, time_position AS ts"
)

ALTITUDE_BANDS = [
    ("En tierra", "on_ground"),
    ("< 1 km", "NOT on_ground AND altitude < 1000"),
    ("1-3 km", "NOT on_ground AND altitude >= 1000 AND altitude < 3000"),
    ("3-6 km", "NOT on_ground AND altitude >= 3000 AND altitude < 6000"),
    ("6-9 km", "NOT on_ground AND altitude >= 6000 AND altitude < 9000"),
    ("9-12 km", "NOT on_ground AND altitude >= 9000 AND altitude < 12000"),
    ("> 12 km", "NOT on_ground AND altitude >= 12000"),
]


class Database:
    def __init__(self, url):
        self.url = url
        self.pool = None
        self.enabled = False

    @contextmanager
    def conn(self):
        with self.pool.connection() as c:
            yield c

    def init(self):
        if not self.url:
            log.warning("DATABASE_URL vacio: historial desactivado")
            return
        try:
            self.pool = ConnectionPool(
                self.url, min_size=1, max_size=8, open=False, timeout=5,
                kwargs={"row_factory": dict_row, "connect_timeout": 5},
            )
            self.pool.open(wait=True, timeout=8)
            self.migrate()
            self.enabled = True
        except Exception as e:  # incluye PoolTimeout, que no es un psycopg.Error
            log.warning("Postgres no disponible, historial desactivado: %s", e)
            if self.pool:
                self.pool.close()

    def migrate(self):
        files = sorted(f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql"))
        with self.conn() as c:
            c.execute("SELECT pg_advisory_xact_lock(8675309)")  # evita migraciones simultaneas
            c.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ DEFAULT now())")
            done = {r["name"] for r in c.execute("SELECT name FROM schema_migrations")}
            for name in files:
                if name in done:
                    continue
                with open(os.path.join(MIGRATIONS_DIR, name), encoding="utf-8") as f:
                    c.execute(f.read())
                c.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (name,))
                log.info("Migracion aplicada: %s", name)

    def _query(self, sql, params=(), default=None):
        """Ejecuta una lectura; ante un error de BD devuelve `default` en vez de romper la peticion."""
        if not self.enabled:
            return default
        try:
            with self.conn() as c:
                return c.execute(sql, params).fetchall()
        except psycopg.Error as e:
            log.warning("Error de BD: %s", e)
            return default

    def _exec(self, sql, params=()):
        if not self.enabled:
            return False
        try:
            with self.conn() as c:
                c.execute(sql, params)
            return True
        except psycopg.Error as e:
            log.warning("Error de BD: %s", e)
            return False

    # --- posiciones ---

    def save_positions(self, flights):
        if not self.enabled or not flights:
            return 0
        rows = [{k: f.get(k) for k in ("id", "cs", "lat", "lon", "alt", "spd", "hdg", "ts", "vr", "sq", "ty", "reg")}
                | {"gnd": bool(f.get("gnd"))} for f in flights]
        try:
            with self.conn() as c, c.cursor() as cur:
                cur.executemany(INSERT, rows)
            return len(rows)
        except psycopg.Error as e:
            log.warning("No se pudo guardar en Postgres: %s", e)
            return 0

    def track(self, icao24, until=None, hours=6):
        """Puntos [lat, lon, alt, ts] de un vuelo; `until` (epoch) corta la trayectoria en un instante pasado."""
        columns = "SELECT latitude, longitude, altitude, time_position FROM positions WHERE icao24 = %s AND "
        if until is None:
            rows = self._query(
                columns + "recorded_at > now() - make_interval(hours => %s) ORDER BY time_position",
                (icao24, hours), default=[])
        else:
            rows = self._query(
                columns + "time_position <= %s AND time_position > %s ORDER BY time_position",
                (icao24, until, until - hours * 3600), default=[])
        return [[r["latitude"], r["longitude"], r["altitude"], r["time_position"]] for r in rows]

    def recent_matches(self, q, limit=10):
        return self._query(
            f"SELECT DISTINCT ON (icao24) {REPLAY_COLUMNS} FROM positions "
            "WHERE (callsign ILIKE %s OR icao24 ILIKE %s OR registration ILIKE %s) "
            "AND recorded_at > now() - interval '1 hour' "
            "ORDER BY icao24, time_position DESC LIMIT %s",
            (f"%{q}%", f"%{q}%", f"%{q}%", limit), default=[],
        )

    # --- reproduccion historica ---

    def replay_range(self):
        rows = self._query("SELECT min(time_position) AS first, max(time_position) AS last FROM positions", default=[])
        return rows[0] if rows and rows[0]["first"] else None

    def replay_at(self, bbox, t, window=90):
        return self._query(
            f"SELECT DISTINCT ON (icao24) {REPLAY_COLUMNS} FROM positions "
            "WHERE time_position BETWEEN %s AND %s AND latitude BETWEEN %s AND %s AND longitude BETWEEN %s AND %s "
            "ORDER BY icao24, time_position DESC",
            (t - window, t, bbox[0], bbox[2], bbox[1], bbox[3]), default=[],
        )

    # --- mantenimiento y estadisticas ---

    def rollup(self):
        """Resume por hora las horas completas (idempotente), antes de que la retencion borre el detalle."""
        done = self._exec(
            "INSERT INTO hourly_stats (hour, flights, positions) "
            "SELECT date_trunc('hour', recorded_at), count(DISTINCT icao24), count(*) FROM positions "
            "WHERE recorded_at < date_trunc('hour', now()) "
            "AND recorded_at >= COALESCE((SELECT max(hour) FROM hourly_stats), '-infinity') GROUP BY 1 "
            "ON CONFLICT (hour) DO UPDATE SET flights = EXCLUDED.flights, positions = EXCLUDED.positions"
        )
        return done and self._exec(
            "INSERT INTO hourly_airlines (hour, airline, flights) "
            "SELECT date_trunc('hour', recorded_at), left(callsign, 3), count(DISTINCT icao24) FROM positions "
            "WHERE callsign ~ '^[A-Z]{3}[0-9]' AND recorded_at < date_trunc('hour', now()) "
            "AND recorded_at >= COALESCE((SELECT max(hour) FROM hourly_airlines), '-infinity') GROUP BY 1, 2 "
            "ON CONFLICT (hour, airline) DO UPDATE SET flights = EXCLUDED.flights"
        )

    def apply_retention(self, days):
        return self._exec("DELETE FROM positions WHERE recorded_at < now() - make_interval(days => %s)", (days,))

    def stats(self, hours):
        per_hour = self._query(
            "SELECT extract(epoch from hour)::bigint AS hour, flights FROM hourly_stats "
            "WHERE hour >= date_trunc('hour', now()) - make_interval(hours => %s) ORDER BY hour", (hours,), default=[])
        live = self._query(
            "SELECT extract(epoch from date_trunc('hour', now()))::bigint AS hour, count(DISTINCT icao24) AS flights "
            "FROM positions WHERE recorded_at >= date_trunc('hour', now())", default=[])
        if live and live[0]["flights"]:
            per_hour.append(live[0])
        airlines = self._query(
            "SELECT airline, sum(flights)::int AS flights FROM hourly_airlines "
            "WHERE hour >= now() - make_interval(hours => %s) GROUP BY airline ORDER BY 2 DESC LIMIT 10",
            (hours,), default=[])
        window = "FROM positions WHERE recorded_at > now() - make_interval(hours => %s)"
        total = self._query(f"SELECT count(*) AS n {window}", (hours,), default=[])
        altitude = []
        if total:
            selects = ", ".join(f"count(*) FILTER (WHERE {cond}) AS b{i}" for i, (_, cond) in enumerate(ALTITUDE_BANDS))
            row = self._query(f"SELECT {selects} {window}", (hours,), default=[])
            if row:
                altitude = [{"band": name, "positions": row[0][f"b{i}"]} for i, (name, _) in enumerate(ALTITUDE_BANDS)]
        return {"per_hour": per_hour, "airlines": airlines, "altitude": altitude, "records": self.records(hours)}

    def records(self, hours):
        """Marcas del periodo: aeronave mas alta y mas rapida, tipo mas visto y total de aeronaves distintas."""
        window = "recorded_at > now() - make_interval(hours => %s)"
        # los topes descartan lecturas absurdas (errores de transponder) que arruinarian el record
        highest = self._query(
            "SELECT icao24, callsign, type_code, altitude FROM positions "
            f"WHERE {window} AND NOT on_ground AND altitude BETWEEN 0 AND 20000 ORDER BY altitude DESC LIMIT 1",
            (hours,), default=[])
        fastest = self._query(
            "SELECT icao24, callsign, type_code, velocity FROM positions "
            f"WHERE {window} AND NOT on_ground AND velocity BETWEEN 0 AND 400 ORDER BY velocity DESC LIMIT 1",
            (hours,), default=[])
        common = self._query(
            "SELECT type_code, count(DISTINCT icao24)::int AS aircraft FROM positions "
            f"WHERE {window} AND type_code IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 1", (hours,), default=[])
        total = self._query(
            f"SELECT count(DISTINCT icao24)::int AS n FROM positions WHERE {window}", (hours,), default=[])
        return {
            "highest": highest[0] if highest else None,
            "fastest": fastest[0] if fastest else None,
            "common_type": common[0] if common else None,
            "aircraft": total[0]["n"] if total else 0,
        }

    # --- lista de seguimiento y alertas ---

    def watchlist(self):
        return self._query("SELECT id, kind, value, label FROM watchlist ORDER BY id", default=[])

    def add_watch(self, kind, value, label):
        rows = self._query(
            "INSERT INTO watchlist (kind, value, label) VALUES (%s, %s, %s) "
            "ON CONFLICT (kind, value) DO UPDATE SET label = EXCLUDED.label RETURNING id, kind, value, label",
            (kind, value, label), default=[])
        return rows[0] if rows else None

    def delete_watch(self, watch_id):
        return self._exec("DELETE FROM watchlist WHERE id = %s", (watch_id,))

    def save_alert(self, kind, watch_id, icao24, callsign, message):
        self._exec(
            "INSERT INTO alert_events (kind, watch_id, icao24, callsign, message) VALUES (%s, %s, %s, %s, %s)",
            (kind, watch_id, icao24, callsign, message))

    def alerts(self, limit=50):
        return self._query(
            "SELECT id, extract(epoch from ts)::bigint AS ts, kind, icao24, callsign, message "
            "FROM alert_events ORDER BY id DESC LIMIT %s", (limit,), default=[])
