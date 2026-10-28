import time

import pytest
import requests

from app.providers import AdsbFi, LocalReceiver, OpenSky, Provider, ProviderChain, ProviderError


class Fake(Provider):
    def __init__(self, name, result=None, fail=False, supported=True):
        super().__init__()
        self.name, self.result, self.fail, self.supported = name, result or [], fail, supported
        self.min_interval = 0
        self.calls = 0

    def supports(self, cell):
        return self.supported

    def fetch(self, cell):
        self.calls += 1
        if self.fail:
            raise ValueError("caido")
        return self.result


def test_chain_falls_back_to_next_provider():
    broken, ok = Fake("a", fail=True), Fake("b", result=[{"id": "x"}])
    flights, source = ProviderChain([broken, ok]).fetch_cell((0, 0))
    assert source == "b" and flights == [{"id": "x"}]
    assert broken.fail_streak == 1 and broken.down_until > 0


def test_failed_provider_is_skipped_while_down():
    broken, ok = Fake("a", fail=True), Fake("b")
    chain = ProviderChain([broken, ok])
    chain.fetch_cell((0, 0))
    chain.fetch_cell((0, 0))
    assert broken.calls == 1  # la segunda vez ni se intenta


def test_provider_recovers_after_success():
    p = Fake("a")
    p.fail_streak, p.down_until = 3, 0
    p.fetch_cell((0, 0))
    assert p.fail_streak == 0 and p.status()["ok"]


def test_chain_raises_when_all_fail():
    with pytest.raises(ProviderError):
        ProviderChain([Fake("a", fail=True), Fake("b", fail=True)]).fetch_cell((0, 0))


def test_chain_skips_unsupported_providers():
    local, remote = Fake("local", supported=False), Fake("remote")
    ProviderChain([local, remote]).fetch_cell((0, 0))
    assert local.calls == 0 and remote.calls == 1


def test_local_receiver_only_covers_cells_in_range():
    receiver = LocalReceiver("http://x/aircraft.json", 40.7, -74.0, 150)
    assert receiver.supports((8, -15))  # contiene la posicion del receptor
    assert not receiver.supports((-9, 30))


class Response:
    def __init__(self, status_code, headers=None):
        self.status_code, self.headers = status_code, headers or {}


def rate_limited_provider(headers):
    provider = AdsbFi()
    provider.min_interval = 0
    provider.session.get = lambda *args, **kwargs: Response(429, headers)
    return provider


def test_429_backs_off_for_the_time_the_source_asks():
    provider = rate_limited_provider({"Retry-After": "33"})
    with pytest.raises(ProviderError):
        provider.fetch_cell((8, -15))
    assert 30 < provider.down_until - time.time() <= 33


def test_429_without_header_uses_default_wait_and_clamps_extremes():
    provider = rate_limited_provider({})
    with pytest.raises(ProviderError):
        provider.fetch_cell((8, -15))
    assert 25 < provider.down_until - time.time() <= 30
    huge = rate_limited_provider({"Retry-After": "99999"})
    with pytest.raises(ProviderError):
        huge.fetch_cell((8, -15))
    assert huge.down_until - time.time() <= 600


def many(n, prefix="a"):
    return [{"id": f"{prefix}{i}", "ts": 100} for i in range(n)]


def test_dense_primary_does_not_ask_a_second_source():
    primary, secondary = Fake("a", result=many(25)), Fake("b", result=many(5, "b"))
    flights, _ = ProviderChain([primary, secondary]).fetch_cell((0, 0))
    assert len(flights) == 25 and secondary.calls == 0


def test_sparse_primary_is_completed_with_second_source():
    primary, secondary = Fake("a", result=many(2)), Fake("b", result=many(9, "b"))
    flights, _ = ProviderChain([primary, secondary]).fetch_cell((0, 0))
    assert len(flights) == 11 and secondary.calls == 1


def test_merge_keeps_newest_position_per_aircraft():
    primary = Fake("a", result=[{"id": "x", "ts": 200, "lat": 1}])
    secondary = Fake("b", result=[{"id": "x", "ts": 100, "lat": 2}])
    flights, _ = ProviderChain([primary, secondary]).fetch_cell((0, 0))
    assert flights == [{"id": "x", "ts": 200, "lat": 1}]


def test_second_opinion_is_throttled_but_reused():
    primary, secondary = Fake("a", result=many(2)), Fake("b", result=many(9, "b"))
    chain = ProviderChain([primary, secondary])
    chain.fetch_cell((0, 0))
    flights, _ = chain.fetch_cell((0, 0))  # inmediatamente despues: no se vuelve a pedir
    assert secondary.calls == 1 and len(flights) == 11  # pero se reutiliza, sin parpadeos


def test_sparse_primary_survives_failing_secondary():
    primary, secondary = Fake("a", result=many(2)), Fake("b", fail=True)
    flights, _ = ProviderChain([primary, secondary]).fetch_cell((0, 0))
    assert len(flights) == 2


def test_opensky_quota_header_sets_the_backoff():
    provider = rate_limited_provider({"X-Rate-Limit-Retry-After-Seconds": "50"})
    with pytest.raises(ProviderError):
        provider.fetch_cell((8, -15))
    assert 45 < provider.down_until - time.time() <= 50


def test_exhausted_primary_hands_over_to_the_next_source_until_it_recovers():
    exhausted, backup = Fake("opensky", fail=True), Fake("adsb.fi", result=many(30, "b"))
    chain = ProviderChain([exhausted, backup])
    assert chain.fetch_cell((0, 0))[1] == "adsb.fi"
    exhausted.fail, exhausted.down_until = False, 0  # se renovo la cuota
    exhausted.result = many(30, "a")
    assert chain.fetch_cell((0, 0))[1] == "opensky"


class JsonResponse:
    def __init__(self, status_code, body=None):
        self.status_code, self.headers, self._body = status_code, {}, body or {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


def test_opensky_requests_a_new_token_after_a_401_and_retries_once():
    provider = OpenSky("id", "secret")
    provider.min_interval = 0
    tokens = iter(["viejo", "nuevo"])
    provider.session.post = lambda *a, **k: JsonResponse(200, {"access_token": next(tokens), "expires_in": 1800})
    used = []

    def get(url, headers=None, **kwargs):
        used.append(headers["Authorization"])
        return JsonResponse(401) if headers["Authorization"] == "Bearer viejo" else JsonResponse(200, {"states": []})

    provider.session.get = get
    assert provider.fetch_cell((0, -15)) == []
    assert used == ["Bearer viejo", "Bearer nuevo"]


def test_opensky_without_credentials_sends_no_authorization():
    provider = OpenSky()
    provider.min_interval = 0
    seen = {}
    provider.session.get = lambda url, headers=None, **kw: seen.update(headers=headers) or JsonResponse(200, {"states": None})
    assert provider.fetch_cell((0, -15)) == [] and seen["headers"] == {}
