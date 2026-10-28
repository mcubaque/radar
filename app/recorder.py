import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.opensky import OpenSkyError

log = logging.getLogger(__name__)


def start_recorder(app):
    """Guarda posiciones de una zona fija cada N segundos, sin depender del navegador."""

    def job():
        try:
            flights = app.opensky.get_flights(app.config["RECORDER_BBOX"])
        except OpenSkyError as e:
            log.warning("Recorder: %s", e)
            return
        app.db.save(flights)

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(job, "interval", seconds=app.config["RECORDER_INTERVAL"], max_instances=1)
    scheduler.start()
    return scheduler
