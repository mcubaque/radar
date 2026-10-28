import time

from app.altitude import height_above_ground_m, pressure_altitude_m
from app.flight import mark_grounded
from app.ground import apply_ground_inference, looks_grounded
from app.store import FlightStore

# Aeropuerto de Bogota: elevacion 2547 m. Un dia con 758,5 hPa en superficie, su altitud de presion es ~2376 m.
BOGOTA = (2547.0, 4.70, -74.14)
BOGOTA_PA = pressure_altitude_m(758.5)


class FakeStatic:
    def __init__(self, airport=BOGOTA):
        self.airport = airport

    def airport_near(self, lat, lon, max_km):
        return self.airport


def flight(**changes):
    return {"id": "abc123", "lat": 4.70, "lon": -74.14, "alt": BOGOTA_PA + 5, "spd": 60, "vr": 0.0,
            "ts": round(time.time())} | changes


def pressure(hpa):
    return lambda lat, lon: hpa


def test_pressure_altitude_matches_the_standard_atmosphere():
    assert abs(pressure_altitude_m(1013.25)) < 1e-6
    assert abs(pressure_altitude_m(226.3) - 11000) < 60
    assert abs(BOGOTA_PA - 2376) < 5


def test_height_above_ground_is_the_difference_and_never_negative():
    assert abs(height_above_ground_m(BOGOTA_PA + 300, 758.5) - 300) < 1e-6
    assert height_above_ground_m(BOGOTA_PA - 80, 758.5) == 0


def test_rolling_on_the_runway_is_grounded_even_if_the_barometric_altitude_is_far_below_the_elevation():
    # la altitud barometrica (~2381 m) esta 166 m POR DEBAJO de la elevacion del aeropuerto, y aun asi es pista
    assert looks_grounded(flight(), FakeStatic(), pressure(758.5))


def test_takeoff_and_final_approach_are_not_grounded():
    assert not looks_grounded(flight(alt=BOGOTA_PA + 90), FakeStatic(), pressure(758.5))  # 90 m de altura, ya volando
    assert not looks_grounded(flight(vr=-4.0), FakeStatic(), pressure(758.5))  # en final: baja ~4 m/s
    assert not looks_grounded(flight(spd=130), FakeStatic(), pressure(758.5))  # demasiado rapido para rodar
    assert not looks_grounded(flight(alt=BOGOTA_PA + 400), FakeStatic(), pressure(758.5))


def test_without_pressure_data_falls_back_to_the_airport_elevation():
    assert looks_grounded(flight(alt=2547 - 86), FakeStatic())  # dentro de +-100 m
    assert not looks_grounded(flight(alt=2547 + 150), FakeStatic())


def test_far_from_any_airport_or_already_grounded_is_left_alone():
    assert not looks_grounded(flight(), FakeStatic(airport=None), pressure(758.5))
    assert not looks_grounded(flight(gnd=1), FakeStatic(), pressure(758.5))
    assert not looks_grounded(flight(alt=None), FakeStatic(), pressure(758.5))


def test_lost_flights_are_grounded_without_checking_vertical_speed():
    descending = flight(vr=-4.0, spd=70)
    assert not looks_grounded(descending, FakeStatic(), pressure(758.5))
    assert looks_grounded(descending, FakeStatic(), pressure(758.5), lost=True)


def test_apply_inference_marks_ground_and_drops_the_misleading_altitude():
    f = flight(vr=0.2)
    apply_ground_inference([f], FakeStatic(), pressure(758.5))
    assert f["gnd"] == 1 and "alt" not in f and "vr" not in f


def test_store_lands_flights_that_stopped_arriving_near_the_runway():
    store = FlightStore()
    now = time.time()
    stale = flight(id="lost", vr=-3.0, ts=round(now) - 40)
    fresh = flight(id="fresh", ts=round(now) - 5)
    store.update_cell((0, -15), [stale, fresh])
    landed = store.land_lost(lambda f: looks_grounded(f, FakeStatic(), pressure(758.5), lost=True), min_age=25, now=now)
    assert landed == 1
    assert store.get("lost")["gnd"] == 1 and "alt" not in store.get("lost")
    assert not store.get("fresh").get("gnd")
    assert store.get("lost")["_v"] == store.version  # los clientes reciben el cambio


def test_mark_grounded_helper():
    f = {"alt": 10, "vr": 1.0, "spd": 5}
    mark_grounded(f)
    assert f == {"gnd": 1, "spd": 5}
