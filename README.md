# SkyMonitor

Mapa de tráfico aéreo en tiempo real hecho solo con datos y herramientas gratuitas. Muestra los aviones de la zona que estés viendo, con ficha de cada vuelo, historial en PostgreSQL, reproducción histórica, estadísticas y alertas.

## Funciones

- **Mapa WebGL (MapLibre)** con miles de aviones fluidos: icono según el tipo (avión, aviación ligera, helicóptero), color por altitud, estelas, movimiento interpolado entre actualizaciones, modo "seguir vuelo", tema claro/oscuro.
- **Tiempo real por SSE**: el servidor consulta las fuentes y reparte solo lo que cambia a cada navegador.
- **Ficha del vuelo**: foto, aerolínea, aeronave, matrícula, origen/destino aproximado, altitud, velocidad, rumbo, velocidad vertical, squawk.
- **Aeropuertos**: búsqueda, clima, llegadas y salidas detectadas, marcadores en el mapa.
- **Búsqueda** de vuelos, matrículas y aeropuertos, con sugerencias y teclado (`/` para enfocar).
- **Filtros** (tipo, altitud, tierra, militares, callsign), lista de vuelos visibles, emergencias resaltadas (squawk 7500/7600/7700).
- **Historial y reproducción** de las zonas grabadas, **estadísticas** (vuelos por hora, aerolíneas, altitudes) y **lista de seguimiento** con alertas por Telegram o correo.
- Capas opcionales: radar de lluvia y anillos de alcance de un receptor ADS-B propio.
- Español e inglés, unidades de aviación o métricas, enlaces compartibles (`#lat,lon,zoom,vuelo`), PWA instalable, accesible por teclado.

## Cómo funciona

```
adsb.lol ─┐                                         ┌─ SSE ──▶ navegadores (MapLibre)
adsb.fi  ─┼─▶ cadena de fuentes ─▶ ingesta ─▶ memoria compartida (por celdas de 5°)
OpenSky  ─┤   (respaldo automático)  (hilo)         └─ grabador ─▶ PostgreSQL ─▶ replay, estadísticas, alertas
receptor ─┘
```

- Los navegadores nunca llaman a las fuentes: 1 o 100 usuarios generan casi las mismas peticiones externas.
- El mundo se divide en celdas de 5°. Solo se refrescan (cada 10 s) las celdas que alguien está viendo o que están grabando.
- Si una fuente falla (o responde 429) se aparta el tiempo que pida (`Retry-After`) o con espera creciente, y se usa la siguiente.
- Los datos de referencia (aeronaves, aeropuertos, rutas, aerolíneas) se descargan una vez a un SQLite local (`data/`): consultarlos no gasta ninguna API.
- Sin PostgreSQL la app sigue funcionando; solo faltan historial, estadísticas y alertas.

## Puesta en marcha (local)

```
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # y ajusta DATABASE_URL
python run.py
```

Abre http://localhost:5000/. La primera vez se descargan ~25 MB de datos de referencia en segundo plano (unos segundos).

Base de datos (opcional): crea la base y pon su URL en `.env`; las tablas se crean solas con las migraciones de `migrations/`.

```
createdb -U postgres radar
```

### Configuración (`.env`)

| Variable | Para qué |
|---|---|
| `DATABASE_URL` | PostgreSQL. Vacío = sin historial |
| `PROVIDERS` | Orden de fuentes (la primera disponible manda; las demás son respaldo): `opensky`, `adsbfi`, `adsblol` |
| `OPENSKY_CLIENT_ID/SECRET` | Credenciales gratuitas de OpenSky: suben la cuota de ~400 a ~4.000 créditos/día |
| `LOCAL_RECEIVER_URL`, `RECEIVER_LAT/LON/RANGE_KM` | Receptor propio (readsb/tar1090): se usa primero en su zona |
| `RECORDER_ENABLED`, `RECORD_ZONES`, `RECORDER_INTERVAL`, `RETENTION_DAYS` | Qué zonas grabar y cuántos días conservar |
| `ADMIN_TOKEN` | Si se define, crear/borrar vigilados exige este token |
| `TELEGRAM_*`, `SMTP_*`, `ALERT_EMAIL_TO` | Canales de aviso para alertas |
| `TRUST_PROXY`, `LOG_JSON` | Para producción detrás de un proxy |

El historial guarda una posición cuando pasaron 30 s, el rumbo cambió 5° o el avión despegó/aterrizó, y un resumen por hora sobrevive a la retención.

## API

`/api/stream` (SSE) · `/api/flights` · `/api/aircraft/<icao24>` · `/api/photo/<icao24>` · `/api/track/<icao24>` · `/api/search` · `/api/airports` · `/api/airport/<código>` · `/api/replay` · `/api/replay/range` · `/api/stats` · `/api/watchlist` · `/api/alerts` · `/api/config` · `/health`

Límite de peticiones por IP (300/min por defecto, 30/min para abrir streams).

## Pruebas y calidad

```
pip install -r requirements-dev.txt
ruff check .
pytest                                  # con TEST_DATABASE_URL definido también prueba contra PostgreSQL
node --test tests/js                    # lógica del mapa
```

La integración continua (GitHub Actions) corre todo esto con un PostgreSQL de servicio.

## Docker

```
echo DB_PASSWORD=cambia-esto >> .env
docker compose up --build
```

Sirve en `127.0.0.1:8000` con `gunicorn` (un solo worker: el estado vive en memoria). El despliegue en servidor, detrás de un proxy inverso, queda pendiente.

## Fuentes de datos y licencias

Vuelos: [adsb.lol](https://adsb.lol) (ODbL) y [adsb.fi](https://adsb.fi), [OpenSky](https://opensky-network.org) opcional · Aeronaves: [tar1090-db](https://github.com/wiedehopf/tar1090-db) · Aeropuertos: [OurAirports](https://ourairports.com) (dominio público) · Rutas: [Virtual Radar Server standing data](https://github.com/vradarserver/standing-data) · Aerolíneas: [OpenFlights](https://openflights.org) · Fotos: [Planespotters](https://www.planespotters.net) · Clima: [Open-Meteo](https://open-meteo.com) y [RainViewer](https://www.rainviewer.com) · Mapa: [OpenFreeMap](https://openfreemap.org), [CARTO](https://carto.com) y OpenStreetMap.

Son servicios comunitarios gratuitos, de uso no comercial y sin garantía de disponibilidad. **Tienen límites**: adsb.lol declara 4 peticiones/s, 60/min y 500/día por IP; adsb.fi pide ~1 petición/s. OpenSky va primero porque es la que más aviones ve en Latinoamérica (sin cuenta ~400 créditos/día; con cuenta gratuita ~4.000); cuando se agota, la app pasa sola a adsb.fi y adsb.lol hasta que se renueve. Cada celda activa cuesta una petición cada 10 s, así que muchas zonas distintas a la vez consumen más cuota. Origen y destino son aproximados (las rutas abiertas pueden estar desactualizadas).

## Licencia

[MIT](LICENSE.md)
