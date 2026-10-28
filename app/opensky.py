import time

import requests

STATES_URL = "https://opensky-network.org/api/states/all"
TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"


class OpenSkyError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


class OpenSkyClient:
    """Cliente minimo de OpenSky con OAuth2 opcional y cache por zona."""

    def __init__(self, client_id="", client_secret="", cache_ttl=10):
        self.client_id = client_id
        self.client_secret = client_secret
        self.cache_ttl = cache_ttl
        self._token = None
        self._token_exp = 0
        self._cache = {}  # bbox -> (timestamp, vuelos)

    def _headers(self):
        if not self.client_id:
            return {}
        if time.time() > self._token_exp - 30:
            r = requests.post(TOKEN_URL, timeout=10, data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            })
            if r.status_code != 200:
                raise OpenSkyError(f"No se pudo autenticar en OpenSky ({r.status_code})")
            body = r.json()
            self._token = body["access_token"]
            self._token_exp = time.time() + body.get("expires_in", 300)
        return {"Authorization": f"Bearer {self._token}"}

    def get_flights(self, bbox):
        """bbox = (lamin, lomin, lamax, lomax). Devuelve lista de dicts."""
        bbox = tuple(round(v, 2) for v in bbox)
        cached = self._cache.get(bbox)
        if cached and time.time() - cached[0] < self.cache_ttl:
            return cached[1]
        try:
            r = requests.get(STATES_URL, headers=self._headers(), timeout=15, params={
                "lamin": bbox[0], "lomin": bbox[1], "lamax": bbox[2], "lomax": bbox[3],
            })
        except requests.RequestException as e:
            raise OpenSkyError(f"OpenSky no responde: {e}") from e
        if r.status_code == 429:
            raise OpenSkyError("Limite de peticiones de OpenSky alcanzado, espera unos segundos", 429)
        if r.status_code != 200:
            raise OpenSkyError(f"OpenSky devolvio {r.status_code}")
        flights = [f for f in map(_parse_state, r.json().get("states") or []) if f]
        self._cache[bbox] = (time.time(), flights)
        return flights

    def cached_flights(self):
        """Todos los vuelos vistos recientemente (para buscar sin gastar cuota)."""
        now = time.time()
        seen = {}
        for ts, flights in self._cache.values():
            if now - ts < 300:
                for f in flights:
                    seen[f["icao24"]] = f
        return list(seen.values())


def _parse_state(s):
    # Orden de campos documentado en la API de OpenSky
    lon, lat = s[5], s[6]
    if lat is None or lon is None:
        return None
    return {
        "icao24": s[0],
        "callsign": (s[1] or "").strip(),
        "country": s[2],
        "time_position": s[3],
        "longitude": lon,
        "latitude": lat,
        "altitude": s[7] if s[7] is not None else s[13],
        "on_ground": bool(s[8]),
        "velocity": s[9],
        "heading": s[10],
        "vertical_rate": s[11],
    }
