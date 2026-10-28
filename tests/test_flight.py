from app.flight import (
    MAX_RADIUS_NM,
    cell_bounds,
    cell_center_radius_nm,
    cells_for_bbox,
    haversine_km,
    normalize_opensky,
    normalize_readsb,
)
from tests.conftest import aircraft


def test_normalize_converts_to_si_units():
    f = normalize_readsb(aircraft(), now=1000)
    assert f["id"] == "abc123" and f["cs"] == "DAL100" and f["reg"] == "N100DL"
    assert f["alt"] == 10668  # 35000 ft
    assert f["spd"] == 231.5  # 450 kt
    assert f["ts"] == 999 and "gnd" not in f


def test_normalize_on_ground_has_no_altitude():
    f = normalize_readsb(aircraft(alt_baro="ground", alt_geom=100))
    assert f["gnd"] == 1 and "alt" not in f


def test_normalize_discards_unusable_aircraft():
    assert normalize_readsb(aircraft(lat=None)) is None
    assert normalize_readsb({"hex": "abc123"}) is None
    assert normalize_readsb(aircraft(seen_pos=120)) is None


def test_normalize_flags_emergency_and_military():
    assert normalize_readsb(aircraft(squawk="7700"))["em"] == 1
    assert normalize_readsb(aircraft(emergency="lifeguard"))["em"] == 1
    assert "em" not in normalize_readsb(aircraft())
    assert normalize_readsb(aircraft(dbFlags=1))["mil"] == 1


def test_normalize_opensky_state():
    state = ["abc123", "UAL5   ", "United States", 1000, 1000, -74.0, 40.7, 3000.0, False, 200.0, 45.0, 1.5,
             None, 3100.0, "7600"]
    f = normalize_opensky(state, now=1000)
    assert f["cs"] == "UAL5" and f["alt"] == 3000 and f["em"] == 1
    assert normalize_opensky(["x", "", "", 0, 0, None, None] + [None] * 8) is None


def test_cells_cover_bbox():
    assert cells_for_bbox((40.4, -74.3, 40.9, -73.7)) == [(8, -15)]
    assert len(cells_for_bbox((38, -80, 45, -70))) == 4  # 2 filas x 2 columnas: los bordes 45 y -70 son exclusivos
    assert len(cells_for_bbox((38, -80, 45.1, -69.9))) == 9


def test_cell_radius_is_within_provider_limit():
    for cell in [(0, 0), (8, -15), (-9, 30), (17, 0)]:
        lat, lon, radius = cell_center_radius_nm(cell)
        assert 0 < radius <= MAX_RADIUS_NM
        lamin, lomin, lamax, lomax = cell_bounds(cell)
        assert lamin < lat < lamax and lomin < lon < lomax


def test_haversine_known_distance():
    assert abs(haversine_km(40.6413, -73.7781, 51.47, -0.4543) - 5540) < 30  # JFK - LHR


def opensky_state(**changes):
    state = ["abc123", "AVA9272 ", "Colombia", 1000, 1000, -74.1, 4.7, 3000.0, False, 200.0, 45.0, 1.5,
             None, 3100.0, "1200", False, 0, 8]
    for index, value in changes.items():
        state[int(index[1:])] = value
    return state


def test_opensky_category_maps_to_adsb_category():
    assert normalize_opensky(opensky_state(i17=8), now=1000)["cat"] == "A7"  # helicoptero
    assert normalize_opensky(opensky_state(i17=2), now=1000)["cat"] == "A1"  # ligero
    assert "cat" not in normalize_opensky(opensky_state(i17=0), now=1000)  # sin informacion
    assert "cat" not in normalize_opensky(opensky_state()[:17], now=1000)  # respuesta sin extended


def test_opensky_discards_stale_positions():
    assert normalize_opensky(opensky_state(), now=1030) is not None
    assert normalize_opensky(opensky_state(), now=1100) is None
