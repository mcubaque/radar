import json
import logging
import threading

from flask import Flask, request
from werkzeug.middleware.proxy_fix import ProxyFix

from app.alerts import AlertManager
from app.db import Database
from app.extensions import limiter
from app.providers import build_chain
from app.recorder import start_scheduler
from app.staticdata import StaticData
from app.store import FlightStore, Ingestor
from config import Config


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "time": self.formatTime(record), "level": record.levelname,
            "logger": record.name, "message": record.getMessage(),
        }, ensure_ascii=False)


def setup_logging(as_json):
    handler = logging.StreamHandler()
    if as_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' https://unpkg.com",
    "style-src 'self' 'unsafe-inline' https://unpkg.com",  # los graficos fijan anchos con style=""
    "img-src 'self' data: blob: https:",
    "font-src 'self' data: https:",
    "connect-src 'self' https:",  # teselas del mapa, estilos y radar
    "worker-src 'self' blob:",
    "child-src blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


def security_headers(response):
    h = response.headers
    h.setdefault("Content-Security-Policy", CSP)
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    h.setdefault("Permissions-Policy", "geolocation=(self), camera=(), microphone=(), payment=()")
    h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    if request.is_secure:  # detras del proxy con HTTPS (TRUST_PROXY=1)
        h.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response


def create_app(config_class=Config, background=True):
    """`background=False` crea la app sin hilos ni tareas (para pruebas)."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    setup_logging(app.config["LOG_JSON"])
    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    limiter.init_app(app)
    app.streams = [0, threading.Lock()]  # conexiones SSE abiertas y su candado

    app.store = FlightStore(cell_ttl=app.config["CELL_TTL"])
    app.chain = build_chain(app.config)
    app.static = StaticData(app.config["DATA_DIR"])
    app.db = Database(app.config["DATABASE_URL"])
    if background:
        app.db.init()
    app.alerts = AlertManager(app.store, app.db, app.config)

    app.after_request(security_headers)

    from app import routes, routes_airports, routes_history  # noqa: F401  (registran sus rutas en el blueprint)
    from app.web import bp
    app.register_blueprint(bp)

    if background:
        app.ingestor = Ingestor(app.store, app.chain, app.static)
        app.ingestor.start()
        app.scheduler = start_scheduler(app)
        if app.config["AUTO_FETCH_STATIC"] and (not app.static.ready or app.static.outdated()):
            threading.Thread(target=app.static.prepare, daemon=True, name="static-data").start()
    return app
