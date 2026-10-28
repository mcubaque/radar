import time

from app.recorder import Recorder, heading_diff
from app.store import FlightStore

ZONE = (40.0, -75.0, 41.0, -73.0)
T0 = round(time.time()) - 600  # timestamps reales: el recorder descarta lo de hace mas de 1 h


class FakeDb:
    def __init__(self):
        self.saved = []

    def save_positions(self, flights):
        self.saved.extend(flights)
        return len(flights)


def make():
    store, db = FlightStore(), FakeDb()
    return Recorder(store, db, [ZONE]), store, db


def test_heading_diff_wraps_around():
    assert heading_diff(359, 1) == 2 and heading_diff(90, 270) == 180


def test_first_sighting_is_saved_then_throttled(flight):
    rec, store, db = make()
    store.update_cell((8, -15), [flight(ts=T0 + 0)])
    rec.tick()
    store.update_cell((8, -15), [flight(ts=T0 + 10)])  # 10 s despues, mismo rumbo
    rec.tick()
    assert len(db.saved) == 1


def test_saves_after_gap_or_heading_change_or_landing(flight):
    rec, store, db = make()
    store.update_cell((8, -15), [flight(ts=T0 + 0, hdg=90)])
    rec.tick()
    store.update_cell((8, -15), [flight(ts=T0 + 12, hdg=100)])  # giro de 10 grados
    rec.tick()
    store.update_cell((8, -15), [flight(ts=T0 + 50, hdg=100)])  # pasaron 38 s
    rec.tick()
    store.update_cell((8, -15), [flight(ts=T0 + 55, hdg=100, gnd=1)])  # aterrizo
    rec.tick()
    assert [f["ts"] - T0 for f in db.saved] == [0, 12, 50, 55]


def test_only_flights_inside_the_zone_are_saved(flight):
    rec, store, db = make()
    store.update_cell((8, -15), [flight(id="in"), flight(id="out", lat=10.0)])
    rec.tick()
    assert [f["id"] for f in db.saved] == ["in"]


def test_zones_are_pinned_so_they_are_fetched_without_viewers():
    _, store, _ = make()
    assert store.due_cells() != []
