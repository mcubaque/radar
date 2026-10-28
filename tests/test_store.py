import threading
import time

from app.store import FlightStore

CELL = (8, -15)
OTHER = (8, -14)


def test_update_cell_replaces_older_positions_only(flight):
    store = FlightStore()
    store.update_cell(CELL, [flight(ts=100, lat=1.0)])
    store.update_cell(OTHER, [flight(ts=90, lat=2.0)])  # mas viejo: se ignora
    assert store.get("abc123")["lat"] == 1.0
    store.update_cell(OTHER, [flight(ts=110, lat=3.0)])
    assert store.get("abc123")["lat"] == 3.0


def test_flight_leaving_its_cell_is_removed(flight):
    store = FlightStore()
    store.update_cell(CELL, [flight()])
    store.update_cell(CELL, [])
    assert store.get("abc123") is None


def test_flight_moved_to_neighbour_cell_is_kept(flight):
    store = FlightStore()
    store.update_cell(CELL, [flight(ts=100)])
    store.update_cell(OTHER, [flight(ts=110)])
    store.update_cell(CELL, [])  # ya no esta en CELL, pero OTHER lo tiene mas reciente
    assert store.get("abc123") is not None


def test_prune_removes_stale(flight):
    store = FlightStore(stale_after=120)
    store.update_cell(CELL, [flight(ts=1000)])
    store.prune(now=1200)
    assert store.get("abc123") is None


def test_due_cells_only_active_and_expired():
    store = FlightStore(cell_ttl=10, active_for=60)
    store.touch([CELL])
    store.pin([OTHER])
    now = time.time()
    assert set(store.due_cells(now)) == {CELL, OTHER}
    store.update_cell(CELL, [], now=now)
    assert store.due_cells(now + 5) == [OTHER]
    assert set(store.due_cells(now + 11)) == {CELL, OTHER}
    assert OTHER in store.due_cells(now + 500) and CELL not in store.due_cells(now + 500)  # CELL dejo de verse


def test_error_schedules_retry_sooner():
    store = FlightStore(cell_ttl=10)
    store.touch([CELL])
    store.mark_error(CELL, "boom", now=100)
    assert store.due_cells(now=104) == []
    assert store.due_cells(now=106) == [CELL]
    assert store.errors([CELL]) == ["boom"]


def test_in_bbox_and_versions(flight):
    store = FlightStore()
    store.update_cell(CELL, [flight(id="a", lat=40.7), flight(id="b", lat=10.0)])
    assert [f["id"] for f in store.in_bbox((40, -75, 41, -73))] == ["a"]
    assert store.get("a")["_v"] == store.version


def test_wait_wakes_on_update(flight):
    store = FlightStore()
    threading.Timer(0.1, lambda: store.update_cell(CELL, [flight()])).start()
    assert store.wait(0, timeout=3) == 1


def test_events_are_numbered_and_bounded():
    store = FlightStore()
    first = store.add_event({"message": "a"})
    store.add_event({"message": "b"})
    assert [e["message"] for e in store.events_after(first["id"])] == ["b"]
