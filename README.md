
---

# SkyMonitor

Breve descripción de tu aplicación aquí.

## Requisitos

- Python (version 3.11.3)
- Flask (version 3.0.0)
- MySQL (version 8.0)
- MySQL-Connector-Python (version 8.2.0)
- OpenSky API (version 1.3.0)

## Instalación

1. Clona este repositorio en tu máquina local.
2. Crea un entorno virtual: `python -m venv venv`
3. Activa el entorno virtual:
   - En Windows: `venv\Scripts\activate`
   - En macOS/Linux: `source venv/bin/activate`
4. Instala las dependencias: `pip install -r requirements.txt`
5. Configura tu base de datos MySQL según lo especificado en `config.py`.

## Uso

1. Ejecuta la aplicación Flask:
   ```
   flask run
   ```
2. Abre tu navegador web y ve a `http://localhost:5000/`.
3. Interactúa con la aplicación según sea necesario.

## Funcionalidades Principales

La aplicación **SkyMonitor** es una herramienta diseñada para obtener y visualizar información en tiempo real sobre el tráfico aéreo en una zona geográfica específica. Utilizando tecnologías como Python, Flask, HTML, JavaScript, MySQL y la API de OpenSky, esta aplicación permite a los usuarios:

- **Visualizar el Tráfico Aéreo en Tiempo Real:** La aplicación muestra en un mapa interactivo la ubicación y detalles de los vuelos en una región determinada. Los usuarios pueden observar la posición, altitud, velocidad y otros datos relevantes de las aeronaves que se encuentran en vuelo.

- **Almacenar Datos en una Base de Datos:** Además de mostrar los vuelos en tiempo real, la aplicación también captura y almacena la información de los vuelos en una base de datos MySQL. Esto permite un registro histórico de los movimientos de las aeronaves, lo que puede ser útil para análisis posteriores o para uso en aplicaciones relacionadas.

- **Actualización Automática de Datos:** La aplicación se conecta a la API de OpenSky para obtener información actualizada sobre el tráfico aéreo en la zona seleccionada. Esta información se actualiza automáticamente a intervalos regulares, lo que garantiza que los datos mostrados sean siempre precisos y actualizados.

La combinación de estas funcionalidades proporciona a los usuarios una herramienta poderosa para monitorear y analizar el tráfico aéreo en una región específica, con aplicaciones potenciales en áreas como la gestión del tráfico aéreo, la planificación de vuelos, la investigación y más.


## Estructura del Proyecto

- `app.py`: Archivo principal de la aplicación Flask.
- `config.py`: Archivo de configuración, incluye la configuración de la base de datos.
- `templates/`: Directorio que contiene los archivos HTML de la aplicación.

## Contribución

¡Contribuciones son bienvenidas! Por favor, abre un issue o envía un pull request.

## Licencia

Este proyecto está bajo la [Licencia MIT](https://github.com/mcubaque/radar/blob/master/LICENSE.md).

---
