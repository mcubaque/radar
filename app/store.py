"""Estado compartido de vuelos en memoria, organizado por celdas de la cuadricula."""
import logging
import threading
import time
from collections import deque
from functools import partial

from app.flight import in_bbox, mark_grounded
from app.ground import LOST_AFTER_S, apply_ground_inference, looks_grounded
from app.media import surface_pressure_hpa
from app.providers import ProviderError

log = logging.getLogger(__name__)

MAX_EVENTS = 100
TRACK_POINTS = 240  # ~40 min a un punto cada 10 s
TRACK_STEP_S = 10


class FlightStore:
    def __init__(self, cell_ttl=10, active_for=120, stale_after=120):
        self.cell_ttl = cell_ttl
        self.active_for = active_for
        self.stale_after = stale_after
        self.flights = {}  # id -> vuelo (con _v y _cell internos)
        self.cells = {}  # celda -> {fetched, touched, pinned, ids, error}
        self.events = []  # alertas recientes para los clientes conectados
        self.version = 0
        self.last_cycle = None
        self.ttl_factor = 1.0  # >1 cuando la fuente principal tiene pocos creditos
        self.meta = {}  # fuente activa y creditos, se envia a los clientes junto a los vuelos
        self.tracks = {}  # id -> deque de [lat, lon, alt, ts] recientes, para la estela sin base de datos
        self._cond = threading.Condition()

    def _cell(self, cell):
        return self.cells.setdefault(
            cell, {"fetched": 0.0, "touched": 0.0, "pinned": False, "ids": set(), "error": None})

    def touch(self, cells):
        now = time.time()
        with self._cond:
            for c in cells:
                self._cell(c)["touched"] = now

    def pin(self, cells):
        with self._cond:
            for c in cells:
                self._cell(c)["pinned"] = True

    def due_cells(self, now=None):
        """Celdas activas (vistas por alguien o fijadas) cuyo dato esta vencido, las mas viejas primero."""
        now = now or time.time()
        ttl = self.cell_ttl * self.ttl_factor
        with self._cond:
            due = [
                (st["fetched"], c) for c, st in self.cells.items()
                if now - st["fetched"] >= ttl and (st["pinned"] or now - st["touched"] < self.active_for)
            ]
        return [c for _, c in sorted(due)]

    def update_cell(self, cell, flights, now=None):
        now = now or time.time()
        with self._cond:
            self.version += 1
            st = self._cell(cell)
            new_ids = set()
            for f in flights:
                new_ids.add(f["id"])
                old = self.flights.get(f["id"])
                if old is None or f["ts"] >= old["ts"]:
                    f["_v"] = self.version
                    f["_cell"] = cell
                    self.flights[f["id"]] = f
                    self._remember(f)
            for gone in st["ids"] - new_ids:  # salio de la cobertura de esta celda
                old = self.flights.get(gone)
                if old and old["_cell"] == cell:
                    del self.flights[gone]
            st.update(fetched=now, ids=new_ids, error=None)
            self.last_cycle = now
            self._cond.notify_all()

    def _remember(self, f):
        track = self.tracks.setdefault(f["id"], deque(maxlen=TRACK_POINTS))
        if not track or f["ts"] - track[-1][3] >= TRACK_STEP_S:
            track.append([f["lat"], f["lon"], f.get("alt"), f["ts"]])

    def track(self, flight_id):
        with self._cond:
            return list(self.tracks.get(flight_id, ()))

    def mark_error(self, cell, error, now=None):
        with self._cond:
            st = self._cell(cell)
            st["fetched"] = (now or time.time()) - self.cell_ttl / 2  # reintenta en la mitad del tiempo
            st["error"] = error

    def prune(self, now=None):
        now = now or time.time()
        with self._cond:
            stale = [i for i, f in self.flights.items() if now - f["ts"] > self.stale_after]
            for i in stale:
                del self.flights[i]
            for i in [i for i in self.tracks if i not in self.flights and now - self.tracks[i][-1][3] > 1800]:
                del self.tracks[i]
            if stale:
                self.version += 1
                self._cond.notify_all()

    def land_lost(self, looks_grounded, min_age, now=None):
        """Marca en tierra los vuelos que dejaron de recibirse hace `min_age` s y parecian estar en pista."""
        now = now or time.time()
        with self._cond:
            landed = [f for f in self.flights.values()
                      if not f.get("gnd") and now - f["ts"] > min_age and looks_grounded(f)]
            if not landed:
                return 0
            self.version += 1
            for f in landed:
                mark_grounded(f)
                f["_v"] = self.version
            self._cond.notify_all()
            return len(landed)

    def in_bbox(self, bbox):
        with self._cond:
            return [f for f in self.flights.values() if in_bbox(f, bbox)]

    def get(self, flight_id):
        return self.flights.get(flight_id)

    def add_event(self, event):
        with self._cond:
            self.version += 1
            event = {**event, "id": self.version}
            self.events = (self.events + [event])[-MAX_EVENTS:]
            self._cond.notify_all()
        return event

    def events_after(self, event_id):
        return [e for e in self.events if e["id"] > event_id]

    def wait(self, last_version, timeout):
        with self._cond:
            if self.version == last_version:
                self._cond.wait(timeout)
            return self.version

    def errors(self, cells):
        return [self.cells[c]["error"] for c in cells if c in self.cells and self.cells[c]["error"]]


class Ingestor(threading.Thread):
    """Hilo que refresca las celdas activas llamando a las fuentes, independiente de los navegadores."""

    def __init__(self, store, chain, static):
        super().__init__(daemon=True, name="ingestor")
        self.store, self.chain, self.static = store, chain, static

    def run(self):
        last_prune = 0.0
        while True:
            if time.time() - last_prune > 5:
                self.store.prune()
                if self.static.ready:
                    lost = partial(looks_grounded, static=self.static, pressure_at=surface_pressure_hpa, lost=True)
                    self.store.land_lost(lost, LOST_AFTER_S)
                last_prune = time.time()
            self.store.ttl_factor = self.chain.slowdown()
            cells = self.store.due_cells()
            if not cells:
                time.sleep(0.5)
            for cell in cells:
                try:
                    flights, source = self.chain.fetch_cell(cell)
                    self.store.meta = {"source": source, "credits": self.chain.credits(), "slow": self.store.ttl_factor}
                except ProviderError as e:
                    self.store.mark_error(cell, str(e))
                else:
                    if self.static.ready:
                        apply_ground_inference(flights, self.static, surface_pressure_hpa)
                    self.store.update_cell(cell, flights)
