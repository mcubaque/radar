"""Prueba de capacidad del stream en vivo: abre N espectadores SSE simultaneos y mide.

    python scripts/loadtest.py --url http://127.0.0.1:8000 --clients 100 --seconds 60

Cada cliente pide la misma zona (Bogota por defecto), cuenta los eventos y mide el tiempo hasta la primera foto
completa. Mientras corre, consulta /api/config cada segundo para medir la latencia del resto de la API.
Hay que ejecutarlo contra la configuracion real (gunicorn gthread en Docker): el servidor de desarrollo de Flask
no es representativo.
"""
import argparse
import statistics
import threading
import time

import requests

ZONE = {"lamin": 3.5, "lomin": -75.5, "lamax": 5.5, "lomax": -73.5}


def viewer(url, deadline, results, index):
    started = time.time()
    first = None
    events = 0
    try:
        with requests.get(f"{url}/api/stream", params=ZONE, stream=True, timeout=(10, 40)) as r:
            if r.status_code != 200:
                results[index] = {"status": r.status_code}
                return
            for line in r.iter_lines():
                if line.startswith(b"event: flights"):
                    events += 1
                    first = first or time.time() - started
                if time.time() > deadline:
                    break
    except requests.RequestException as e:
        results[index] = {"status": type(e).__name__}
        return
    results[index] = {"status": 200, "first": first, "events": events}


def api_latency(url, deadline, samples):
    while time.time() < deadline:
        t0 = time.time()
        try:
            requests.get(f"{url}/api/config", timeout=10)
            samples.append(time.time() - t0)
        except requests.RequestException:
            samples.append(10.0)
        time.sleep(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--clients", type=int, default=100)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--ramp", type=float, default=0.05, help="segundos entre conexiones")
    args = parser.parse_args()

    deadline = time.time() + args.seconds
    results = [None] * args.clients
    samples = []
    threads = [threading.Thread(target=api_latency, args=(args.url, deadline, samples), daemon=True)]
    for i in range(args.clients):
        threads.append(threading.Thread(target=viewer, args=(args.url, deadline, results, i), daemon=True))
    for t in threads:
        t.start()
        time.sleep(args.ramp)
    for t in threads:
        t.join(args.seconds + 60)

    done = [r for r in results if r]
    ok = [r for r in done if r["status"] == 200 and r.get("first") is not None]
    refused = [r["status"] for r in done if r["status"] != 200]
    reasons = sorted(set(map(str, refused)))
    print(f"Espectadores: {args.clients} pedidos, {len(ok)} con datos, {len(refused)} fallidos {reasons}")
    if ok:
        firsts = sorted(r["first"] for r in ok)
        p95 = firsts[max(0, int(len(firsts) * .95) - 1)]
        print(f"Primera foto: mediana {statistics.median(firsts):.2f} s, p95 {p95:.2f} s")
        print(f"Eventos por espectador: mediana {statistics.median(r['events'] for r in ok):.0f}")
    if samples:
        samples.sort()
        print(f"/api/config durante la carga: mediana {statistics.median(samples) * 1000:.0f} ms, "
              f"max {samples[-1] * 1000:.0f} ms ({len(samples)} muestras)")


if __name__ == "__main__":
    main()
