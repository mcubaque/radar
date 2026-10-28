import os
import time

import pytest

from app import create_app
from config import Config


def aircraft(hex_id="abc123", **overrides):
    """Un avion tal como lo entrega readsb/adsb.lol."""
    base = {"hex": hex_id, "flight": "DAL100  ", "r": "N100DL", "t": "B739", "category": "A3", "lat": 40.7, "lon": -74.0,
            "alt_baro": 35000, "gs": 450, "track": 90, "baro_rate": 0, "squawk": "1234", "seen_pos": 1.0}
    return base | overrides


@pytest.fixture
def app(tmp_path):
    class TestConfig(Config):
        TESTING = True
        DATABASE_URL = ""
        DATA_DIR = str(tmp_path)
        RECORDER_ENABLED = False
        RATELIMIT_ENABLED = False
        ADMIN_TOKEN = ""

    return create_app(TestConfig, background=False)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def flight():
    def make(**overrides):
        base = {"id": "abc123", "cs": "DAL100", "lat": 40.7, "lon": -74.0, "alt": 10000, "spd": 230.0, "hdg": 90,
                "ts": round(time.time())}
        return base | overrides
    return make


@pytest.fixture(scope="session")
def test_database_url():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL no definido")
    return url
