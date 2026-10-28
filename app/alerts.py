"""Lista de seguimiento y alertas de emergencia (squawk 7500/7600/7700)."""
import logging
import smtplib
import time
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage

import requests

log = logging.getLogger(__name__)

COOLDOWN = 6 * 3600  # no repetir la misma alerta para el mismo avion antes de 6 h
EMERGENCY_TEXT = {"7500": "secuestro", "7600": "falla de radio", "7700": "emergencia general"}
KIND_FIELD = {"callsign": "cs", "icao24": "id", "registration": "reg", "squawk": "sq"}


class AlertManager:
    def __init__(self, store, db, config):
        self.store, self.db, self.config = store, db, config
        self._watch = []
        self._watch_loaded = 0.0
        self._notified = {}  # clave -> epoch de la ultima alerta
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="notify")

    def reload_watchlist(self):
        self._watch = self.db.watchlist()
        self._watch_loaded = time.time()

    def check(self):
        if time.time() - self._watch_loaded > 30:
            self.reload_watchlist()
        now = time.time()
        self._notified = {k: t for k, t in self._notified.items() if now - t < COOLDOWN}
        for f in list(self.store.flights.values()):
            if f.get("em") and f.get("sq") in EMERGENCY_TEXT:
                self._fire(("em", f["id"], f["sq"]), f, "emergency", None,
                           f"Emergencia {f['sq']} ({EMERGENCY_TEXT[f['sq']]}): {f.get('cs') or f['id']}")
            for w in self._watch:
                value = f.get(KIND_FIELD[w["kind"]])
                if value and value.upper() == w["value"].upper():
                    self._fire(("w", w["id"], f["id"]), f, "watch", w["id"],
                               f"{w['label'] or w['value']} detectado: {f.get('cs') or f['id']}")

    def _fire(self, key, flight, kind, watch_id, message):
        if key in self._notified:
            return
        self._notified[key] = time.time()
        event = self.store.add_event({
            "kind": kind, "icao24": flight["id"], "callsign": flight.get("cs"), "message": message,
            "lat": flight["lat"], "lon": flight["lon"], "ts": round(time.time()),
        })
        self.db.save_alert(kind, watch_id, flight["id"], flight.get("cs"), message)
        log.info("Alerta: %s", message)
        self._pool.submit(self._notify, event["message"])

    def _notify(self, text):
        cfg = self.config
        if cfg["TELEGRAM_BOT_TOKEN"] and cfg["TELEGRAM_CHAT_ID"]:
            try:
                requests.post(
                    f"https://api.telegram.org/bot{cfg['TELEGRAM_BOT_TOKEN']}/sendMessage",
                    json={"chat_id": cfg["TELEGRAM_CHAT_ID"], "text": f"✈ SkyMonitor: {text}"}, timeout=10,
                ).raise_for_status()
            except requests.RequestException as e:
                log.warning("Telegram fallo: %s", type(e).__name__)
        if cfg["SMTP_HOST"] and cfg["ALERT_EMAIL_TO"]:
            msg = EmailMessage()
            msg["Subject"] = f"SkyMonitor: {text}"
            msg["From"] = cfg["SMTP_USER"] or cfg["ALERT_EMAIL_TO"]
            msg["To"] = cfg["ALERT_EMAIL_TO"]
            msg.set_content(text)
            try:
                with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=15) as s:
                    s.starttls()
                    if cfg["SMTP_USER"]:
                        s.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
                    s.send_message(msg)
            except (OSError, smtplib.SMTPException) as e:
                log.warning("Correo fallo: %s", type(e).__name__)
