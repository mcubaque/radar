from app.alerts import AlertManager
from app.store import FlightStore


class FakeDb:
    def __init__(self, watch=()):
        self.watch, self.alerts = list(watch), []

    def watchlist(self):
        return self.watch

    def save_alert(self, *args):
        self.alerts.append(args)


def manager(db, flights):
    store = FlightStore()
    store.update_cell((8, -15), flights)
    cfg = {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": "", "SMTP_HOST": "", "ALERT_EMAIL_TO": ""}
    return AlertManager(store, db, cfg), store


def test_emergency_squawk_alerts_once(flight):
    m, store = manager(FakeDb(), [flight(sq="7700", em=1)])
    m.check()
    m.check()  # misma emergencia: no se repite
    assert len(store.events) == 1 and "7700" in store.events[0]["message"]


def test_watchlist_match_is_case_insensitive(flight):
    db = FakeDb([{"id": 1, "kind": "callsign", "value": "dal100", "label": "Mi vuelo"}])
    m, store = manager(db, [flight(cs="DAL100")])
    m.check()
    assert store.events[0]["message"].startswith("Mi vuelo detectado")
    assert db.alerts and db.alerts[0][0] == "watch"


def test_no_match_no_alert(flight):
    db = FakeDb([{"id": 1, "kind": "callsign", "value": "UAL9", "label": None}])
    m, store = manager(db, [flight(cs="DAL100")])
    m.check()
    assert store.events == []
