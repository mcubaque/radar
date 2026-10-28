"""Pruebas contra un PostgreSQL real. Se omiten si TEST_DATABASE_URL no esta definido."""
import time

import pytest

from app.db import Database

BBOX = (40.0, -75.0, 41.0, -73.0)


@pytest.fixture
def db(test_database_url):
    database = Database(test_database_url)
    database.init()
    assert database.enabled
    with database.conn() as c:
        c.execute("TRUNCATE positions, hourly_stats, hourly_airlines, watchlist, alert_events RESTART IDENTITY")
    yield database
    database.pool.close()


def position(flight, **overrides):
    return flight(gnd=None, vr=0.0, sq="1200", ty="B739", reg="N1") | overrides


def test_migrations_are_idempotent(db):
    db.migrate()  # una segunda vez no falla ni repite
    with db.conn() as c:
        names = [r["name"] for r in c.execute("SELECT name FROM schema_migrations ORDER BY name")]
    assert names == sorted(set(names)) and len(names) >= 2


def test_save_positions_ignores_duplicates(db, flight):
    f = position(flight)
    assert db.save_positions([f]) == 1
    db.save_positions([f])  # mismo (icao24, time_position)
    with db.conn() as c:
        assert c.execute("SELECT count(*) AS n FROM positions").fetchone()["n"] == 1


def test_track_returns_ordered_points_until_instant(db, flight):
    now = int(time.time())
    db.save_positions([position(flight, ts=now - 100 + i * 10, lat=40.0 + i / 10) for i in range(5)])
    assert len(db.track("abc123")) == 5
    assert len(db.track("abc123", until=now - 70)) == 4
    assert db.track("zzzzzz") == []


def test_replay_returns_latest_position_per_aircraft_in_bbox(db, flight):
    t = int(time.time()) - 500
    db.save_positions([
        position(flight, id="a", ts=t - 30, lat=40.1), position(flight, id="a", ts=t, lat=40.2),
        position(flight, id="b", ts=t, lat=10.0),  # fuera de la zona
        position(flight, id="c", ts=t - 300),  # fuera de la ventana de 90 s
    ])
    frame = db.replay_at(BBOX, t)
    assert [(f["id"], f["lat"]) for f in frame] == [("a", 40.2)]
    assert db.replay_range()["last"] == t


def test_rollup_stats_and_retention(db, flight):
    with db.conn() as c:  # horas pasadas, para que cuenten como completas
        c.execute(
            "INSERT INTO positions (icao24, callsign, latitude, longitude, altitude, on_ground, time_position, recorded_at) "
            "SELECT 'a' || i, 'DAL' || i, 40, -74, 1000, false, 1000 + i, now() - interval '3 hours' FROM generate_series(1, 4) i")
        c.execute(
            "INSERT INTO positions (icao24, callsign, latitude, longitude, altitude, on_ground, time_position, recorded_at) "
            "VALUES ('old', 'UAL1', 40, -74, 1000, false, 5, now() - interval '30 days')")
    assert db.rollup()
    stats = db.stats(24)
    assert sum(h["flights"] for h in stats["per_hour"]) >= 4
    assert stats["airlines"][0] == {"airline": "DAL", "flights": 4}
    assert sum(a["positions"] for a in stats["altitude"]) == 4  # la fila de hace 30 dias queda fuera de la ventana
    db.apply_retention(7)
    with db.conn() as c:
        assert c.execute("SELECT count(*) AS n FROM positions WHERE icao24 = 'old'").fetchone()["n"] == 0
    assert db.stats(24)["airlines"][0]["flights"] == 4  # el resumen sobrevive a la retencion


def test_watchlist_and_alert_history(db):
    item = db.add_watch("callsign", "DAL100", "Mi vuelo")
    assert db.add_watch("callsign", "DAL100", "Otro nombre")["id"] == item["id"]  # no duplica
    assert [w["label"] for w in db.watchlist()] == ["Otro nombre"]
    db.save_alert("watch", item["id"], "abc123", "DAL100", "DAL100 detectado")
    assert db.alerts()[0]["message"] == "DAL100 detectado"
    db.delete_watch(item["id"])
    assert db.watchlist() == []


def test_unreachable_database_degrades_gracefully():
    database = Database("postgresql://nadie:x@127.0.0.1:1/nada")
    database.init()
    assert not database.enabled
    assert database.save_positions([{"id": "a"}]) == 0 and database.track("a") == [] and database.watchlist() == []


def test_records_ignore_absurd_readings(db, flight):
    with db.conn() as c:
        c.execute(
            "INSERT INTO positions (icao24, callsign, type_code, latitude, longitude, altitude, velocity, on_ground, time_position) VALUES "
            "('a1', 'DAL1', 'B739', 40, -74, 11000, 250, false, 1), "
            "('a2', 'UAL2', 'A388', 40, -74, 13000, 280, false, 2), "
            "('bad', 'BAD1', 'B739', 40, -74, 99999, 9999, false, 3), "
            "('g1', 'GND1', 'B739', 40, -74, 500, 390, true, 4)")
    r = db.records(24)
    assert r["highest"]["icao24"] == "a2" and r["fastest"]["icao24"] == "a2"
    assert r["common_type"] == {"type_code": "B739", "aircraft": 3} and r["aircraft"] == 4
