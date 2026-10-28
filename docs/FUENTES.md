# Fuentes de datos: condiciones de uso

Antes de publicar SkyMonitor abiertamente hay que revisar esto. Se distingue lo **verificado** (leído en la fuente el 28-10-2026) de lo **por verificar**.

| Fuente | Uso | Condiciones |
|---|---|---|
| **adsb.fi** (vuelos) | Verificado | "Para uso personal y no comercial". No se puede vender ni licenciar el dato. Límite público de 1 petición/s; el abuso (muchos 4xx/429) provoca bloqueo temporal de IP. **Hay que citar a adsb.fi con enlace a su portada** (ya se hace en la atribución del mapa). Servicio "tal cual", puede suspenderse. Para más volumen o uso comercial, contactarlos. |
| **adsb.lol** (vuelos) | Por verificar | Su página de documentación no muestra condiciones. La licencia del dato se cree ODbL (exige atribución y compartir en las mismas condiciones). Los límites los anuncia en cabeceras: 4/s, 60/min, 500/día. Leer su política antes de publicar. |
| **OpenSky** (vuelos) | Por verificar | La documentación de la API solo describe cuotas (créditos por nivel: anónimo, estándar, feeder activo, con licencia) y el `429` al agotarse. Sus condiciones de uso están en otra página y, por lo que se conoce, orientan los datos a investigación y uso no comercial: **revisar los términos de la cuenta antes de exponer la app públicamente**, porque una web pública con muchos visitantes consume la cuota de una sola cuenta. |
| **NOAA Aviation Weather** (METAR, TAF, SIGMET) | Por verificar | Datos del gobierno de EE. UU., sin clave. No se encontró una cláusula restrictiva, pero la API pide no abusar; la app cachea 5 min. |
| **Open-Meteo** (clima, viento) | Por verificar | Gratuito para uso no comercial con límite diario; para uso comercial exige plan de pago. |
| **RainViewer** (radar) | Por verificar | Gratuito con atribución. |
| **Planespotters** (fotos) | Por verificar | Las fotos son de sus autores: se muestra el crédito y el enlace, y no se copian a disco más allá de la caché de metadatos. |
| **EOX Sentinel-2 cloudless 2016** (imagen satelital) | Verificado | Licencia CC BY 4.0 (la capa `s2cloudless_3857`): permite uso incluso comercial con atribución, incluida en el mapa. Las ediciones 2017 y posteriores son CC BY-NC-SA: no usarlas si la app se abre al público. |
| **AWS Terrain Tiles** (relieve) | Por verificar | Datos abiertos (Mapzen/AWS); piden atribución, incluida en el mapa. |
| **OurAirports, tar1090-db, OpenFlights, Virtual Radar Server** | Dominio público / abiertas | Se descargan una vez y se consultan en local. |
| **LiveATC** | Solo enlace | No se incrusta ni se retransmite audio: solo hay un enlace de búsqueda. No cubre todos los aeropuertos (p. ej. SKBO no está). |

## Qué implica

- Mientras la app sea **personal o para un grupo reducido**, todo lo anterior encaja.
- Si se abre al **público general**, el riesgo real es la cuota de OpenSky (una sola cuenta compartida por todos los visitantes) y las cláusulas de "no comercial". Tener publicidad, cobrar o presentarlo como producto lo empeora.
- Mitigaciones ya implementadas: caché agresiva, espaciado automático al bajar los créditos, `MAX_STREAMS`, respaldo entre fuentes y atribución visible.
- Mitigación futura si crece: un receptor ADS-B propio (alimenta además a las redes comunitarias y sube la cuota de OpenSky).
