import json
import logging
import threading

from flask import Flask
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


def create_app(config_class=Config, background=True):
    """`background=False` crea la app sin hilos ni tareas (para pruebas)."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    setup_logging(app.config["LOG_JSON"])
    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    limiter.init_app(app)

    app.store = FlightStore(cell_ttl=app.config["CELL_TTL"])
    app.chain = build_chain(app.config)
    app.static = StaticData(app.config["DATA_DIR"])
    app.db = Database(app.config["DATABASE_URL"])
    if background:
        app.db.init()
    app.alerts = AlertManager(app.store, app.db, app.config)

    from app.routes import bp
    app.register_blueprint(bp)

    if background:
        app.ingestor = Ingestor(app.store, app.chain, app.static)
        app.ingestor.start()
        app.scheduler = start_scheduler(app)
        if app.config["AUTO_FETCH_STATIC"] and not app.static.ready:
            threading.Thread(target=app.static.prepare, daemon=True, name="static-data").start()
    return app
