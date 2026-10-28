# Operación

Guía para llevar SkyMonitor a un servidor (aún sin desplegar). Todo está pensado para Docker Compose en un VPS (Hetzner).

## Arquitectura de ejecución

- `app`: gunicorn con **un solo worker** (`gthread`). El estado de vuelos vive en memoria y lo comparten los hilos, así que no se puede escalar con más workers.
- Cada espectador en vivo (SSE) ocupa **un hilo**. `WEB_THREADS` (200) marca el tope técnico y `MAX_STREAMS` (150) el tope aplicado: los espectadores 151 en adelante reciben `503` y el resto de la API sigue respondiendo.
- Un cliente que se va se detecta cuando falla la siguiente escritura (cada ≤15 s hay un ping), así que su hilo tarda hasta ~30 s en liberarse.
- `db`: PostgreSQL 17 con volumen propio.

## Puesta en marcha

```
cp .env.example .env     # definir DB_PASSWORD, ADMIN_TOKEN, OPENSKY_*, TRUST_PROXY=1, LOG_JSON=1
docker compose up -d --build
```

`ADMIN_TOKEN` debe definirse en servidor: sin él cualquiera puede añadir elementos a la lista de seguimiento y leerla.

## Proxy inverso

La app escucha solo en `127.0.0.1:8000`. Hay ejemplos listos en `deploy/`:

- `deploy/nginx.conf.example` (HTTPS con Let's Encrypt).
- `deploy/Caddyfile.example` (HTTPS automático).

Lo imprescindible para el tiempo real: **`/api/stream` sin buffering** (`proxy_buffering off` en nginx, `flush_interval -1` en Caddy) y tiempo de lectura largo. Con `TRUST_PROXY=1` la app confía en `X-Forwarded-*` para la IP del limitador y para HSTS.

> Los repositorios de SIGF y HU Tracker no incluyen la configuración del proxy del servidor; antes de desplegar hay que copiar de allí el patrón real (dominio, certificados, red de Docker).

## Copias de seguridad

`scripts/backup.sh` hace `pg_dump` comprimido en `./backups` y borra las de más de 14 días:

```
30 3 * * * cd /opt/radar && ./scripts/backup.sh
```

Restaurar: `gunzip -c backups/radar-AAAAMMDD-HHMM.sql.gz | docker compose exec -T db psql -U radar radar`. Conviene copiar `backups/` fuera del servidor.

## Vigilancia

`scripts/healthcheck.sh` consulta `/health` y avisa por Telegram (si `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` están en el entorno) al caer y al recuperarse. Cuenta como fallo: sin respuesta, `status` distinto de `ok` o ingesta parada más de 180 s.

```
*/5 * * * * RADAR_URL=http://127.0.0.1:8000 /opt/radar/scripts/healthcheck.sh
```

`/api/status` muestra la fuente activa, los créditos de OpenSky, el ritmo de actualización y los espectadores conectados.

## Logs

`LOG_JSON=1` emite JSON por línea. `docker-compose.yml` rota los logs de los contenedores (10 MB × 5 archivos).

## Prueba de capacidad

```
python scripts/loadtest.py --url http://127.0.0.1:8000 --clients 100 --seconds 60
```

Abre N espectadores SSE simultáneos y mide el tiempo hasta la primera foto, los eventos recibidos y la latencia del resto de la API durante la carga. Para medir desde una sola IP hay que arrancar con `DISABLE_RATELIMIT=1` (el límite de 30 streams/min por IP lo bloquearía).

Resultado de la validación local (servidor de desarrollo de Flask en Windows, **no representativo de gunicorn**): 120 espectadores simultáneos conectaron sin errores, primera foto en ~0,01 s con la caché caliente y `/api/config` respondió en 8 ms de mediana con la carga activa. Con 150 ya abiertos, los siguientes recibieron `503` como se espera. **Pendiente: repetir contra el contenedor real en Linux** antes del despliegue.
