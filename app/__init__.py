import logging

from flask import Flask

from app.db import Database
from app.opensky import OpenSkyClient
from app.recorder import start_recorder
from config import Config


def create_app(config_class=Config):
    logging.basicConfig(level=logging.INFO)
    app = Flask(__name__)
    app.config.from_object(config_class)

    app.opensky = OpenSkyClient(
        app.config["OPENSKY_CLIENT_ID"],
        app.config["OPENSKY_CLIENT_SECRET"],
        app.config["CACHE_TTL"],
    )
    app.db = Database(app.config["DATABASE_URL"])
    app.db.init()

    from app.routes import bp
    app.register_blueprint(bp)

    if app.config["RECORDER_ENABLED"] and app.db.enabled:
        start_recorder(app)
    return app
