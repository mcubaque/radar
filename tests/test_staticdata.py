import gzip

import pytest

from app.staticdata import StaticData, build_static_db

AIRPORTS_HEADER = ('"id","ident","type","name","latitude_deg","longitude_deg","elevation_ft","continent","iso_country",'
                   '"iso_region","municipality","scheduled_service","icao_code","iata_code","gps_code","local_code",'
                   '"home_link","wikipedia_link","keywords"\n')


@pytest.fixture
def static(tmp_path):
    raw = tmp_path / "static" / "raw"
    raw.mkdir(parents=True)
    with gzip.open(raw / "aircraft.csv.gz", "wt", encoding="utf-8") as f:
        f.write("A1B2C3;N123AB;B739;00;BOEING 737-900;2014;ACME LEASING;\n")
    (raw / "airports.csv").write_text(
        AIRPORTS_HEADER
        + '1,"KJFK","large_airport","John F Kennedy Intl",40.64,-73.78,13,"NA","US","US-NY","New York","yes","KJFK","JFK","KJFK","JFK",,,\n'
        + '2,"KTPA","large_airport","Tampa Intl",27.97,-82.53,26,"NA","US","US-FL","Tampa","yes","KTPA","TPA","KTPA","TPA",,,\n'
        + '3,"KATL","large_airport","Hartsfield-Jackson",33.64,-84.43,1026,"NA","US","US-GA","Atlanta","yes","KATL","ATL","KATL","ATL",,,\n'
        + '4,"HELI","heliport","Pad",1,1,0,"NA","US","US-NY","X","no",,,,,,,\n',
        encoding="utf-8",
    )
    with gzip.open(raw / "routes.csv.gz", "wt", encoding="utf-8-sig") as f:
        f.write("Callsign,Code,Number,AirlineCode,AirportCodes\n"
                "DAL1,DAL,1,DAL,KJFK-KTPA\nDAL2,DAL,2,DAL,KJFK-KTPA-KJFK\n")
    (raw / "airport-frequencies.csv").write_text(
        chr(10).join([
            '"id","airport_ref","airport_ident","type","description","frequency_mhz"',
            '1,1,"KJFK","TWR","KENNEDY TWR",119.1',
            '2,1,"KJFK","ATIS","ATIS",115.1',
            '3,1,"KJFK","GND","GND",121.9',
            '4,1,"KJFK","XYZ","OTHER",100.5',
            '5,1,"KJFK","TWR","TWR ALT",123.9',
        ]) + chr(10),
        encoding="utf-8",
    )
    (raw / "runways.csv").write_text(chr(10).join([
        'id,airport_ref,airport_ident,length_ft,width_ft,surface,lighted,closed,le_ident,le_latitude_deg,le_longitude_deg,le_elevation_ft,le_heading_degT,le_displaced_threshold_ft,he_ident,he_latitude_deg,he_longitude_deg,he_elevation_ft,he_heading_degT,he_displaced_threshold_ft',
        '1,1,KJFK,12079,200,ASP,1,0,04L,40.62,-73.79,13,31,,22R,40.65,-73.76,13,211,',
        '2,1,KJFK,5000,100,ASP,1,1,13,40.6,-73.8,13,,,31,40.61,-73.78,13,,',
    ]) + chr(10), encoding="utf-8")
    (raw / "airlines.dat").write_text(
        '2009,"Delta Air Lines",\\N,"DL","DAL","DELTA","United States","Y"\n'
        '9,"Dead Air",\\N,"XX","DED","X","Nowhere","N"\n',
        encoding="utf-8",
    )
    data = StaticData(str(tmp_path))
    build_static_db(str(raw), data.path)
    return data


def test_aircraft_lookup(static):
    row = static.aircraft("a1b2c3")
    assert row["reg"] == "N123AB" and row["description"] == "BOEING 737-900" and row["owner"] == "ACME LEASING"
    assert static.aircraft("000000") is None


def test_airport_lookup_by_any_code_and_excludes_heliports(static):
    assert static.airport("jfk")["name"] == "John F Kennedy Intl"
    assert static.airport("KJFK")["iata"] == "JFK"
    assert static.airport("HELI") is None


def test_search_airports(static):
    assert static.search_airports("tampa")[0]["iata"] == "TPA"
    assert static.search_airports("JFK")[0]["icao"] == "KJFK"


def test_airline_from_callsign_and_inactive_ignored(static):
    assert static.airline("DAL123")["name"] == "Delta Air Lines"
    assert static.airline("N123AB") is None
    assert static.airline("DED1") is None


def test_route_two_legs_and_multi_leg_choice(static):
    assert static.route_codes("DAL1") == ("KJFK", "KTPA")
    assert static.route_codes("DAL2") is None  # varios tramos sin posicion: no se adivina
    assert static.route_codes("DAL2", 38.0, -78.0) == ("KJFK", "KTPA")  # yendo de Nueva York a Tampa
    assert static.route_codes("DAL2", 28.5, -81.0) == ("KJFK", "KTPA")  # llegando a Tampa
    assert static.route_codes("DAL2", 28.0, -82.4) == ("KJFK", "KTPA")
    assert static.route("DAL1")["destination"]["iata"] == "TPA"


def test_route_is_discarded_when_the_aircraft_is_not_on_it(static):
    # DAL1 es KJFK-KTPA, pero este avion esta sobre Bogota: el numero de vuelo se reutilizo en otra ruta
    assert static.route_codes("DAL1", 4.6, -74.1) is None
    assert static.route("DAL1", 4.6, -74.1) is None
    assert static.route_codes("DAL1", 33.0, -80.0) == ("KJFK", "KTPA")  # sobre la costa de Georgia/Carolina
    assert static.route_codes("DAL1") == ("KJFK", "KTPA")  # sin posicion no se puede validar, pero hay un solo tramo


def test_nearest_airport_reference_for_ground_detection(static):
    elevation, lat, lon = static.airport_near(40.65, -73.79, 4.0)  # a ~1.5 km del KJFK
    assert round(elevation) == 4 and abs(lat - 40.64) < 0.01  # 13 ft
    assert static.airport_near(41.5, -73.0, 4.0) is None  # lejos de cualquier aeropuerto


def test_airports_in_bbox_respects_rank(static):
    found = static.airports_in_bbox((20, -90, 45, -70), max_rank=0)
    assert {a["iata"] for a in found} == {"JFK", "TPA", "ATL"}


def test_not_ready_returns_empty(tmp_path):
    empty = StaticData(str(tmp_path / "nada"))
    assert not empty.ready and empty.aircraft("a1b2c3") is None and empty.search_airports("x") == []


def test_route_found_when_callsign_has_leading_zeros(static):
    # los aviones transmiten DAL001 pero la tabla de rutas guarda DAL1
    assert static.route_codes("DAL001") == ("KJFK", "KTPA")
    assert static.route_codes("DAL0001") == ("KJFK", "KTPA")


def test_frequencies_come_ordered_by_role_then_value(static):
    assert [(f["type"], f["mhz"]) for f in static.frequencies("KJFK")] == [
        ("ATIS", 115.1), ("GND", 121.9), ("TWR", 119.1), ("TWR", 123.9), ("XYZ", 100.5)]
    assert static.frequencies("NOPE") == []


def test_runways_carry_their_ends_and_width_and_skip_closed_ones(static):
    [rw] = static.runways("KJFK")
    assert (rw["le_ident"], rw["he_ident"], rw["width_ft"]) == ("04L", "22R", 200)
    assert (rw["le_lat"], rw["he_lon"]) == (40.62, -73.76)


def test_runways_near_finds_the_closest_airports_first(static):
    near = static.runways_near(40.64, -73.78)
    assert [a["ident"] for a in near] == ["KJFK"] and len(near[0]["runways"]) == 1
    assert near[0]["elevation_ft"] == 13
    assert static.runways_near(0, 0) == []
