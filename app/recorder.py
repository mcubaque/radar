"""Tareas periodicas: grabar historial (solo si cambia), resumir por hora y aplicar retencion."""
import logging
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.flight import cells_for_bbox

log = logging.getLogger(__name__)

MIN_SAVE_GAP = 30  # s entre posiciones guardadas de un mismo vuelo, salvo cambios relevantes
HEADING_DELTA = 5  # grados de cambio de rumbo que fuerzan guardar


def heading_diff(a, b):
    return abs((a - b + 180) % 360 - 180)


class Recorder:
    """Guarda una posicion cuando pasaron 30 s o el avion cambio de rumbo o de estado en tierra."""

    def __init__(self, store, db, zones):
        self.store, self.db, self.zones = store, db, zones
        self._last = {}  # id -> (ts, hdg, gnd) de lo ultimo guardado
        self.store.pin([c for z in zones for c in cells_for_bbox(z)])

    def should_save(self, f):
        prev = self._last.get(f["id"])
        if prev is None:
            return True
        ts, hdg, gnd = prev
        if f["ts"] <= ts:
            return False
        if f["ts"] - ts >= MIN_SAVE_GAP or bool(f.get("gnd")) != gnd:
            return True
        return hdg is not None and f.get("hdg") is not None and heading_diff(f["hdg"], hdg) >= HEADING_DELTA

    def tick(self):
        seen = {}
        for zone in self.zones:
            for f in self.store.in_bbox(zone):
                seen[f["id"]] = f
        to_save = [f for f in seen.values() if self.should_save(f)]
        saved = self.db.save_positions(to_save)
        if saved:
            for f in to_save:
                self._last[f["id"]] = (f["ts"], f.get("hdg"), bool(f.get("gnd")))
        cutoff = time.time() - 3600
        self._last = {i: v for i, v in self._last.items() if v[0] > cutoff}
        return saved


def start_scheduler(app):
    cfg = app.config
    scheduler = BackgroundScheduler(daemon=True)
    if cfg["RECORDER_ENABLED"] and app.db.enabled and cfg["RECORD_ZONES"]:
        recorder = Recorder(app.store, app.db, cfg["RECORD_ZONES"])
        scheduler.add_job(recorder.tick, "interval", seconds=cfg["RECORDER_INTERVAL"], max_instances=1)
        scheduler.add_job(app.db.rollup, "interval", minutes=30, max_instances=1, next_run_time=datetime.now())
        scheduler.add_job(
            lambda: (app.db.rollup(), app.db.apply_retention(cfg["RETENTION_DAYS"])),
            "cron", hour=3, minute=30, max_instances=1,
        )
    if app.db.enabled:
        scheduler.add_job(app.alerts.check, "interval", seconds=10, max_instances=1)
    scheduler.start()
    return scheduler
