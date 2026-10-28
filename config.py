import os

from dotenv import load_dotenv

load_dotenv()


def _bbox(value):
    lamin, lomin, lamax, lomax = (float(x) for x in value.split(","))
    return lamin, lomin, lamax, lomax


class Config:
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    OPENSKY_CLIENT_ID = os.getenv("OPENSKY_CLIENT_ID", "")
    OPENSKY_CLIENT_SECRET = os.getenv("OPENSKY_CLIENT_SECRET", "")
    # Segundos que se reutiliza una respuesta de OpenSky para la misma zona
    CACHE_TTL = int(os.getenv("CACHE_TTL", "10"))
    RECORDER_ENABLED = os.getenv("RECORDER_ENABLED", "0") == "1"
    RECORDER_INTERVAL = int(os.getenv("RECORDER_INTERVAL", "30"))
    RECORDER_BBOX = _bbox(os.getenv("RECORDER_BBOX", "40.4774,-74.2591,40.9176,-73.7004"))
