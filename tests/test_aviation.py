import time

import pytest

from app import aviation
from app.airfield import runway_in_use
from app.providers import OpenSky, ProviderChain

RUNWAY = {"le_ident": "13", "le_hdg": 130.0, "he_ident": "31", "he_hdg": 310.0, "lat": 40.64, "lon": -73.78}


def landing(heading, **kw):
    return {"id": "x", "lat": 40.64, "lon": -73.78, "alt": 300, "hdg": heading, "spd": 70, **kw}


def test_runway_in_use_picks_the_end_most_aircraft_are_aligned_with():
    flights = [landing(131), landing(128), landing(310)]
    assert runway_in_use([RUNWAY], flights, 3) == "13"


def test_runway_in_use_needs_enough_evidence_and_ignores_high_or_slow_traffic():
    assert runway_in_use([RUNWAY], [landing(130)], 3) is None
    cruising = [landing(130, alt=9000), landing(130, alt=9000)]
    taxiing = [landing(130, gnd=1, spd=5), landing(130, gnd=1, spd=5)]
    assert runway_in_use([RUNWAY], cruising + taxiing, 3) is None


def test_runway_in_use_ignores_traffic_off_the_runway_axis():
    far_side = [landing(130, lat=40.64 + 0.1), landing(130, lat=40.64 + 0.1)]
    assert runway_in_use([RUNWAY], far_side, 3) is None


def test_pressure_level_follows_altitude():
    assert aviation.pressure_level(0) == 1000
    assert aviation.pressure_level(11000) == 250
    assert aviation.pressure_level(5500) == 500


def test_cached_remembers_failures_only_briefly(monkeypatch):
    aviation._cache.clear()
    calls = []

    def boom():
        calls.append(1)
        raise ValueError("x")

    assert aviation._cached("k", 300, boom) is None
    assert aviation._cached("k", 300, boom) is None
    assert len(calls) == 1  # el segundo intento usa el fallo recordado
    aviation._cache["k"] = (time.time() - aviation.RETRY - 1, None)
    aviation._cached("k", 300, boom)
    assert len(calls) == 2


def test_sigmets_skip_expired_and_degenerate_areas(monkeypatch):
    aviation._cache.clear()
    ring = [{"lon": 0, "lat": 0}, {"lon": 1, "lat": 0}, {"lon": 1, "lat": 1}]
    now = time.time()
    monkeypatch.setattr(aviation, "_get", lambda url, **p: [
        {"hazard": "TS", "top": 40000, "validTimeTo": now + 600, "coords": ring, "firName": "X"},
        {"hazard": "TURB", "validTimeTo": now - 600, "coords": ring},
        {"hazard": "ICE", "validTimeTo": now + 600, "coords": ring[:2]},
    ] if "isigmet" in url else [])
    features = aviation.sigmets()["features"]
    assert [f["properties"]["hazard"] for f in features] == ["TS"]
    ring = features[0]["geometry"]["coordinates"][0][0]
    assert ring[0] == ring[-1]  # el anillo queda cerrado


@pytest.mark.parametrize("credits, factor", [(None, 1.0), (5000, 1.0), (500, 2.0), (100, 4.0)])
def test_chain_slows_down_as_opensky_credits_run_low(credits, factor):
    sky = OpenSky()
    sky.credits = credits
    assert ProviderChain([sky]).slowdown() == factor


def test_opensky_reads_remaining_credits_header():
    class R:
        headers = {"X-Rate-Limit-Remaining": "3999"}

    sky = OpenSky()
    sky._read_quota(R())
    assert sky.credits == 3999 and sky.status()["credits"] == 3999


def test_store_keeps_recent_positions_spaced_by_time(app, flight):
    store = app.store
    store.update_cell((0, 0), [flight(ts=1000)])
    store.update_cell((0, 0), [flight(ts=1004, lon=-73.99)])  # menos de 10 s: no se anota
    store.update_cell((0, 0), [flight(ts=1012, lon=-73.98)])
    assert [p[3] for p in store.track("abc123")] == [1000, 1012]


def test_sigmet_with_several_areas_becomes_a_multipolygon(monkeypatch):
    aviation._cache.clear()
    ring = [{"lon": 0, "lat": 0}, {"lon": 1, "lat": 0}, {"lon": 1, "lat": 1}]
    monkeypatch.setattr(aviation, "_get", lambda url, **p: [
        {"hazard": "VA", "validTimeTo": time.time() + 600, "coords": [ring, ring], "geom": "AREAS"},
    ] if "isigmet" in url else [])
    geometry = aviation.sigmets()["features"][0]["geometry"]
    assert geometry["type"] == "MultiPolygon" and len(geometry["coordinates"]) == 2
