import json

import pytest

from app import media
from app.extensions import limiter

NY = "lamin=40.0&lomin=-75.0&lamax=41.0&lomax=-73.0"
CELL = (8, -15)


class FakeStatic:
    ready = True

    def aircraft(self, icao24):
        return {"reg": "N100DL", "type": "B739", "description": "BOEING 737-900", "owner": "ACME", "year": "2014"}

    def airline(self, callsign):
        return {"icao": "DAL", "name": "Delta Air Lines", "country": "US"} if callsign.startswith("DAL") else None

    def route(self, callsign, lat=None, lon=None):
        return {"origin": {"iata": "JFK"}, "destination": {"iata": "TPA"}}

    def route_codes(self, callsign, lat=None, lon=None):
        return ("KATL", "KJFK") if callsign == "DAL100" else ("KJFK", "KTPA")

    def search_airports(self, q, limit=6):
        return [{"iata": "JFK", "name": "Kennedy"}] if q == "jfk" else []

    def airport(self, code):
        return {"icao": "KJFK", "ident": "KJFK", "iata": "JFK", "lat": 40.64, "lon": -73.78, "name": "Kennedy"} if code.upper() == "JFK" else None


@pytest.fixture
def seeded(app, flight):
    app.static = FakeStatic()
    app.store.update_cell(CELL, [
        flight(id="abc123", cs="DAL100", lat=40.7, lon=-74.0),
        flight(id="def456", cs="UAL7", lat=40.64, lon=-73.78, gnd=1),
        flight(id="aaa111", cs="DAL200", lat=60.0, lon=10.0),
    ])
    return app


def test_flights_returns_only_requested_area_without_internal_keys(seeded, client):
    data = client.get(f"/api/flights?{NY}").get_json()
    assert {f["id"] for f in data} == {"abc123", "def456"}
    assert all(not k.startswith("_") for f in data for k in f)


@pytest.mark.parametrize("query", ["lamin=x", "lamin=41&lomin=-75&lamax=40&lomax=-73", "lamin=-95&lomin=0&lamax=10&lomax=10"])
def test_flights_rejects_bad_bbox(client, query):
    assert client.get(f"/api/flights?{query}").status_code == 400


def test_flights_rejects_zones_too_large(client):
    response = client.get("/api/flights?lamin=-60&lomin=-170&lamax=60&lomax=170")
    assert response.status_code == 400 and response.get_json()["code"] == "too_large"


def test_stream_sends_full_snapshot_first(seeded, client):
    response = client.get(f"/api/stream?{NY}", buffered=False)
    chunks = iter(response.response)
    assert next(chunks) == b"retry: 3000\n\n"
    event = next(chunks).decode()
    assert event.startswith("event: flights")
    payload = json.loads(event.split("data: ", 1)[1])
    assert payload["full"] is True and {f["id"] for f in payload["flights"]} == {"abc123", "def456"}
    assert response.headers["Content-Type"].startswith("text/event-stream")
    response.close()


def test_health_and_config(client):
    health = client.get("/health").get_json()
    assert health["database"] is False and "providers" in health
    assert client.get("/api/config").get_json()["history"] is False


def test_search_matches_flights_and_airports(seeded, client):
    result = client.get("/api/search?q=dal1").get_json()
    assert [f["id"] for f in result["flights"]] == ["abc123"]
    assert client.get("/api/search?q=jfk").get_json()["airports"][0]["iata"] == "JFK"
    assert client.get("/api/search?q=a").get_json() == {"flights": [], "airports": []}


def test_aircraft_detail(seeded, client):
    data = client.get("/api/aircraft/abc123").get_json()
    assert data["aircraft"]["registration"] == "N100DL" and data["airline"]["name"] == "Delta Air Lines"
    assert data["route"]["destination"]["iata"] == "TPA"
    assert client.get("/api/aircraft/zzz").status_code == 400


def test_airport_lists_arrivals(seeded, client, monkeypatch):
    monkeypatch.setattr(media, "weather_at", lambda lat, lon: {"temperature_2m": 15})
    data = client.get("/api/airport/jfk").get_json()
    assert [f["cs"] for f in data["arriving"]] == ["DAL100"]
    assert data["ground"] == 1 and data["weather"]["temperature_2m"] == 15
    assert client.get("/api/airport/nope").status_code == 404


def test_reference_returns_surface_pressure(client, monkeypatch):
    monkeypatch.setattr(media, "weather_at", lambda lat, lon: {"surface_pressure": 758.5})
    assert client.get("/api/reference?lat=4.7&lon=-74.1").get_json() == {"surface_hpa": 758.5}
    monkeypatch.setattr(media, "weather_at", lambda lat, lon: None)
    assert client.get("/api/reference?lat=4.7&lon=-74.1").get_json() == {"surface_hpa": None}
    assert client.get("/api/reference?lat=x").status_code == 400
    assert client.get("/api/reference?lat=99&lon=0").status_code == 400


@pytest.mark.parametrize("path", ["/api/replay/range", "/api/stats", "/api/watchlist"])
def test_history_endpoints_need_database(client, path):
    assert client.get(path).status_code == 503


class FakeDb:
    enabled = True

    def __init__(self):
        self.items = []

    def watchlist(self):
        return self.items

    def add_watch(self, kind, value, label):
        item = {"id": len(self.items) + 1, "kind": kind, "value": value, "label": label}
        self.items.append(item)
        return item

    def delete_watch(self, watch_id):
        self.items = [i for i in self.items if i["id"] != watch_id]


def post(client, body, token=None):
    headers = {"X-Admin-Token": token} if token else {}
    return client.post("/api/watchlist", json=body, headers=headers)


def test_watchlist_validation(app, client):
    app.db = FakeDb()
    assert post(client, {"kind": "callsign", "value": "dal100"}).get_json()["value"] == "DAL100"
    assert post(client, {"kind": "bogus", "value": "dal100"}).status_code == 400
    assert post(client, {"kind": "callsign", "value": "x;drop"}).status_code == 400
    assert post(client, {"kind": "squawk", "value": "7700"}).status_code == 400


def test_watchlist_label_null_is_stored_as_empty_not_the_text_none(app, client):
    app.db = FakeDb()
    assert post(client, {"kind": "callsign", "value": "HK4541", "label": None}).get_json()["label"] is None
    assert post(client, {"kind": "callsign", "value": "HK4542", "label": ""}).get_json()["label"] is None


def test_watchlist_writes_require_admin_token_when_configured(app, client):
    app.db = FakeDb()
    app.config["ADMIN_TOKEN"] = "secreto"
    assert post(client, {"kind": "callsign", "value": "DAL100"}).status_code == 401
    assert post(client, {"kind": "callsign", "value": "DAL100"}, token="mal").status_code == 401
    assert post(client, {"kind": "callsign", "value": "DAL100"}, token="secreto").status_code == 201
    assert client.get("/api/watchlist").status_code == 200  # leer es libre
    assert client.delete("/api/watchlist/1").status_code == 401
    assert client.delete("/api/watchlist/1", headers={"X-Admin-Token": "secreto"}).status_code == 204


def test_rate_limit_returns_429(app, client):
    app.config["RATELIMIT_ENABLED"] = True
    app.config["RATELIMIT_DEFAULT"] = "2 per minute"
    limiter.enabled = True
    limiter.init_app(app)
    try:
        codes = [client.get("/api/config").status_code for _ in range(3)]
        assert codes == [200, 200, 429]
        assert client.get("/health").status_code == 200  # /health esta exento
    finally:
        limiter.enabled = False
        limiter.reset()
