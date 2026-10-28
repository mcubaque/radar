"""Fuentes de vuelos intercambiables con respaldo automatico."""
import logging
import threading
import time

import requests

from app.flight import (
    cell_bounds,
    cell_center_radius_nm,
    haversine_km,
    normalize_opensky,
    normalize_readsb,
)

log = logging.getLogger(__name__)

UA = "SkyMonitor/1.0 (proyecto personal; https://github.com/mcubaque/radar)"


class ProviderError(Exception):
    pass


class RateLimited(requests.RequestException):
    """La fuente respondio 429; `retry_after` son los segundos que pide esperar."""

    def __init__(self, retry_after):
        super().__init__(f"limite de peticiones (429), reintentar en {retry_after}s")
        self.retry_after = retry_after


class Provider:
    name = ""
    min_interval = 0.5  # segundos minimos entre peticiones (cortesia con servicios gratuitos)

    def __init__(self):
        self._lock = threading.Lock()
        self._last_call = 0.0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = UA
        self.last_ok = None
        self.last_error = None
        self.fail_streak = 0
        self.down_until = 0.0

    def supports(self, cell):
        return True

    def fetch(self, cell):
        raise NotImplementedError

    def fetch_cell(self, cell):
        with self._lock:  # serializa y espacia las peticiones de esta fuente
            wait = self._last_call + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
        try:
            flights = self.fetch(cell)
        except (requests.RequestException, ValueError, KeyError, IndexError) as e:
            self.last_error = f"{type(e).__name__}: {e}"
            self.fail_streak += 1
            backoff = getattr(e, "retry_after", None) or min(300, 15 * 2 ** (self.fail_streak - 1))
            self.down_until = time.time() + backoff
            raise ProviderError(f"{self.name}: {self.last_error}") from e
        self.last_ok = time.time()
        self.fail_streak = 0
        self.down_until = 0.0
        return flights

    def status(self):
        return {
            "name": self.name,
            "ok": self.fail_streak == 0,
            "last_ok": self.last_ok,
            "last_error": self.last_error,
        }

    def _read_quota(self, response):
        """Gancho para fuentes que informan de su cuota en las cabeceras."""

    def _get_json(self, url, **kwargs):
        r = self.session.get(url, timeout=15, **kwargs)
        self._read_quota(r)
        if r.status_code == 429:
            # OpenSky avisa con su propia cabecera cuando se agotan los creditos del dia
            header = r.headers.get("X-Rate-Limit-Retry-After-Seconds") or r.headers.get("Retry-After", "")
            raise RateLimited(min(600, max(5, int(header))) if header.isdigit() else 30)
        r.raise_for_status()
        return r.json()


class _ReadsbProvider(Provider):
    """adsb.lol y adsb.fi hablan el mismo formato que readsb."""

    url = ""
    list_keys = ("ac", "aircraft")

    def fetch(self, cell):
        lat, lon, radius = cell_center_radius_nm(cell)
        data = self._get_json(self.url.format(lat=lat, lon=lon, radius=radius))
        now = time.time()
        raw = next((data[k] for k in self.list_keys if k in data), [])
        return [f for f in (normalize_readsb(a, now) for a in raw) if f]


class AdsbLol(_ReadsbProvider):
    name = "adsb.lol"
    min_interval = 0.3
    url = "https://api.adsb.lol/v2/point/{lat}/{lon}/{radius}"


class AdsbFi(_ReadsbProvider):
    name = "adsb.fi"
    min_interval = 1.1  # su API anuncia ~1 peticion por segundo
    url = "https://opendata.adsb.fi/api/v2/lat/{lat}/lon/{lon}/dist/{radius}"


class LocalReceiver(_ReadsbProvider):
    """Receptor propio (readsb/tar1090). Solo cubre las celdas dentro de su alcance."""

    name = "receptor propio"
    min_interval = 0.5

    def __init__(self, url, lat, lon, range_km):
        super().__init__()
        self.url, self.lat, self.lon, self.range_km = url, lat, lon, range_km

    def supports(self, cell):
        lamin, lomin, lamax, lomax = cell_bounds(cell)
        if lamin <= self.lat <= lamax and lomin <= self.lon <= lomax:
            return True
        corners = [(la, lo) for la in (lamin, lamax) for lo in (lomin, lomax)]
        points = [((lamin + lamax) / 2, (lomin + lomax) / 2), *corners]
        return any(haversine_km(self.lat, self.lon, *p) <= self.range_km for p in points)

    def fetch(self, cell):
        data = self._get_json(self.url)
        now = time.time()
        return [f for f in (normalize_readsb(a, now) for a in data.get("aircraft", [])) if f]


class OpenSky(Provider):
    name = "opensky"
    min_interval = 2.0
    states_url = "https://opensky-network.org/api/states/all"
    track_url = "https://opensky-network.org/api/tracks/all"
    token_url = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"

    def __init__(self, client_id="", client_secret=""):
        super().__init__()
        self.client_id, self.client_secret = client_id, client_secret
        self._token, self._token_exp = None, 0
        self.credits = None  # creditos que quedan hoy, segun X-Rate-Limit-Remaining
        self._tracks = {}  # icao24 -> (instante, puntos)

    def _read_quota(self, response):
        remaining = response.headers.get("X-Rate-Limit-Remaining", "")
        if remaining.isdigit():
            self.credits = int(remaining)

    def status(self):
        return {**super().status(), "credits": self.credits}

    def _headers(self):
        if not self.client_id:
            return {}
        if time.time() > self._token_exp - 30:
            r = self.session.post(self.token_url, timeout=10, data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            })
            r.raise_for_status()
            body = r.json()
            self._token = body["access_token"]
            self._token_exp = time.time() + body.get("expires_in", 300)
        return {"Authorization": f"Bearer {self._token}"}

    def fetch(self, cell):
        lamin, lomin, lamax, lomax = cell_bounds(cell)
        params = {"lamin": lamin, "lomin": lomin, "lamax": lamax, "lomax": lomax, "extended": 1}
        try:
            data = self._get_json(self.states_url, headers=self._headers(), params=params)
        except requests.HTTPError as e:
            if e.response is None or e.response.status_code != 401:
                raise
            self._token_exp = 0  # 401: el token vencio o fue revocado; se pide uno nuevo y se reintenta una vez
            data = self._get_json(self.states_url, headers=self._headers(), params=params)
        now = time.time()
        return [f for f in (normalize_opensky(s, now) for s in data.get("states") or []) if f]

    def track(self, icao24):
        """Trayectoria del vuelo en curso desde que despego, como [lat, lon, alt, ts]; [] si OpenSky no la tiene."""
        cached = self._tracks.get(icao24)
        if cached and time.time() - cached[0] < TRACK_CACHE_S:
            return cached[1]
        try:
            data = self._get_json(self.track_url, headers=self._headers(), params={"icao24": icao24, "time": 0})
        except (requests.RequestException, RateLimited, ValueError):
            return []
        path = (data or {}).get("path") or []
        points = [[p[1], p[2], p[3], p[0]] for p in path if p[1] is not None and p[2] is not None]
        self._tracks[icao24] = (time.time(), points)
        return points


def merge(*lists):
    """Une listas de vuelos dejando, por aeronave, la posicion mas reciente."""
    merged = {}
    for flights in lists:
        for f in flights:
            if f["id"] not in merged or f["ts"] >= merged[f["id"]]["ts"]:
                merged[f["id"]] = f
    return list(merged.values())


SPARSE = 20  # menos aviones que esto en una celda: se pide una segunda opinion a otra fuente
SECOND_OPINION_EVERY = 20  # segundos entre segundas opiniones de una misma celda (cuida la cuota)
EXTRA_MAX_AGE = 60  # segundos que se reutiliza la ultima segunda opinion
TRACK_CACHE_S = 120  # una trayectoria de OpenSky se reutiliza este tiempo
LOW_CREDITS = 800 # con menos creditos de OpenSky se espacian las peticiones (x2, y x4 bajo la cuarta parte)


class ProviderChain:
    """Prueba las fuentes en orden; una que falla se aparta un tiempo.

    Donde hay pocos aviones (poca cobertura comunitaria) una sola fuente puede ver mucho menos que otra,
    asi que las celdas escasas se completan con una segunda fuente, fusionando por aeronave.
    """

    def __init__(self, providers):
        self.providers = providers
        self._extra = {}  # celda -> (instante, vuelos de la segunda opinion)
        self.active = None  # nombre de la fuente que respondio en la ultima peticion

    def credits(self):
        """Creditos restantes de la fuente con cuota conocida (OpenSky), o None."""
        return next((p.credits for p in self.providers if getattr(p, "credits", None) is not None), None)

    def slowdown(self):
        """Factor por el que alargar el tiempo entre refrescos para no agotar la cuota del dia."""
        credits = self.credits()
        if credits is None or credits >= LOW_CREDITS:
            return 1.0
        return 4.0 if credits < LOW_CREDITS / 4 else 2.0

    def _usable(self, cell):
        now = time.time()
        return [p for p in self.providers if p.supports(cell) and now >= p.down_until]

    def fetch_cell(self, cell):
        errors = []
        candidates = self._usable(cell)
        for i, p in enumerate(candidates):
            try:
                primary, source = p.fetch_cell(cell), p.name
            except ProviderError as e:
                errors.append(str(e))
                log.warning("Fuente caida: %s", e)
                continue
            self.active = source
            if len(primary) >= SPARSE:
                return primary, source
            return self._with_second_opinion(cell, primary, candidates[i + 1:], source)
        raise ProviderError("; ".join(errors) or "ninguna fuente disponible")

    def _with_second_opinion(self, cell, primary, others, source):
        taken_at, extra = self._extra.get(cell, (0.0, []))
        now = time.time()
        if now - taken_at >= SECOND_OPINION_EVERY:
            for p in others:
                try:
                    extra, taken_at = p.fetch_cell(cell), now
                    break
                except ProviderError as e:
                    log.warning("Fuente caida: %s", e)
            self._extra[cell] = (taken_at, extra)
        if now - taken_at > EXTRA_MAX_AGE:
            return primary, source
        return merge(extra, primary), source

    def track(self, icao24):
        """Trayectoria desde el despegue, si alguna fuente la ofrece (hoy solo OpenSky)."""
        source = next((p for p in self.providers if hasattr(p, "track")), None)
        return source.track(icao24) if source else []

    def status(self):
        return [p.status() for p in self.providers]


def build_chain(config):
    providers = []
    if config.get("LOCAL_RECEIVER_URL"):
        providers.append(LocalReceiver(
            config["LOCAL_RECEIVER_URL"], config["RECEIVER_LAT"], config["RECEIVER_LON"], config["RECEIVER_RANGE_KM"],
        ))
    available = {
        "adsblol": AdsbLol,
        "adsbfi": AdsbFi,
        "opensky": lambda: OpenSky(config["OPENSKY_CLIENT_ID"], config["OPENSKY_CLIENT_SECRET"]),
    }
    for name in config["PROVIDERS"]:
        if name in available:
            providers.append(available[name]())
        else:
            log.warning("Fuente desconocida en PROVIDERS: %s", name)
    return ProviderChain(providers)
