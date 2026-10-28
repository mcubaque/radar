import os

from dotenv import load_dotenv

load_dotenv()


def _bbox(value):
    lamin, lomin, lamax, lomax = (float(x) for x in value.split(","))
    return lamin, lomin, lamax, lomax


def _zones(value):
    """'lamin,lomin,lamax,lomax;lamin,...' -> lista de bbox"""
    return [_bbox(v) for v in value.split(";") if v.strip()]


def _flag(name, default="0"):
    return os.getenv(name, default) == "1"


class Config:
    DEBUG = _flag("FLASK_DEBUG")
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))

    # Fuentes de vuelos, en orden de preferencia: opensky, adsbfi, adsblol
    PROVIDERS = [p.strip() for p in os.getenv("PROVIDERS", "opensky,adsbfi,adsblol").split(",") if p.strip()]
    OPENSKY_CLIENT_ID = os.getenv("OPENSKY_CLIENT_ID", "")
    OPENSKY_CLIENT_SECRET = os.getenv("OPENSKY_CLIENT_SECRET", "")

    # Receptor ADS-B propio (readsb/tar1090): URL de aircraft.json y su posicion
    LOCAL_RECEIVER_URL = os.getenv("LOCAL_RECEIVER_URL", "")
    RECEIVER_LAT = float(os.getenv("RECEIVER_LAT", "0") or 0)
    RECEIVER_LON = float(os.getenv("RECEIVER_LON", "0") or 0)
    RECEIVER_RANGE_KM = float(os.getenv("RECEIVER_RANGE_KM", "400"))

    CELL_TTL = float(os.getenv("CELL_TTL", "10"))  # segundos entre refrescos de cada celda
    MAX_CELLS = int(os.getenv("MAX_CELLS", "16"))  # celdas maximas por vista
    MAX_STREAMS = int(os.getenv("MAX_STREAMS", "150"))  # espectadores simultaneos; mas reciben 503
    MIN_ZOOM = int(os.getenv("MIN_ZOOM", "6"))
    AUTO_FETCH_STATIC = _flag("AUTO_FETCH_STATIC", "1")

    # Historial
    RECORDER_ENABLED = _flag("RECORDER_ENABLED")
    RECORDER_INTERVAL = int(os.getenv("RECORDER_INTERVAL", "15"))
    RECORD_ZONES = _zones(os.getenv("RECORD_ZONES", "40.4774,-74.2591,40.9176,-73.7004"))
    RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "7"))

    # Alertas (todo opcional)
    ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "")

    LOG_JSON = _flag("LOG_JSON")
    TRUST_PROXY = _flag("TRUST_PROXY")
    RATELIMIT_ENABLED = not _flag("DISABLE_RATELIMIT")  # solo para pruebas de carga desde una IP
    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "300 per minute")
