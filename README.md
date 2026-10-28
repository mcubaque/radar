# SkyMonitor

Mini clon de Flight Radar: mapa en tiempo real con los aviones de la zona que estés viendo, usando la API pública de [OpenSky](https://opensky-network.org). Opcionalmente guarda el historial en PostgreSQL para dibujar la trayectoria de cada vuelo.

## Funciones

- Mapa Leaflet que pide los vuelos de la zona visible (se actualiza al mover/zoom y cada 10 s, sin recargar la página).
- Iconos de avión rotados según el rumbo; los aviones en tierra salen en gris.
- Click en un avión: datos y trayectoria guardada (requiere Postgres + recorder).
- Búsqueda por callsign o icao24 entre los vuelos vistos recientemente.
- Autenticación OAuth2 de OpenSky opcional (más cuota de peticiones).
- Si Postgres no está disponible la app sigue funcionando, solo sin historial.

## Instalación

```
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # y edita los valores
```

### Base de datos (opcional)

```
createdb -U postgres radar
```

Pon la contraseña en `DATABASE_URL` dentro de `.env`. La tabla `positions` se crea sola al arrancar.
Para grabar posiciones en segundo plano usa `RECORDER_ENABLED=1` (zona definida en `RECORDER_BBOX`).

## Uso

```
python run.py
```

Abre http://localhost:5000/

## Estructura

- `run.py`: punto de entrada.
- `config.py`: configuración desde variables de entorno (`.env`).
- `app/__init__.py`: `create_app()`.
- `app/routes.py`: endpoints `/api/flights`, `/api/track/<icao24>`, `/api/search`.
- `app/opensky.py`: cliente de OpenSky (OAuth2 + cache por zona).
- `app/db.py`: acceso a Postgres. `app/recorder.py`: grabación periódica con APScheduler.
- `app/static/`, `app/templates/`: frontend.

## Limitaciones

OpenSky no da origen/destino, matrícula ni modelo, y su cobertura y cuota son limitadas comparadas con Flight Radar 24.

## Licencia

[MIT](LICENSE.md)
