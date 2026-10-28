import { $$ } from './util.js';
import { state } from './state.js';

const es = {
    'search.placeholder': 'Buscar vuelo, matrícula o aeropuerto', 'search.none': 'Sin resultados',
    'toolbar.label': 'Herramientas', 'tool.menu': 'Herramientas',
    'tool.locate': 'Mi ubicación', 'tool.list': 'Vuelos visibles', 'tool.filters': 'Filtros', 'tool.layers': 'Capas',
    'tool.replay': 'Reproducción histórica', 'tool.stats': 'Estadísticas', 'tool.watch': 'Seguimiento y alertas', 'tool.settings': 'Ajustes',
    'common.close': 'Cerrar', 'common.copied': 'Enlace copiado', 'common.error': 'Algo salió mal',
    'status.connecting': 'Conectando…', 'status.live': 'En vivo', 'status.flights': '{n} vuelos', 'status.reconnecting': 'Reconectando…',
    'status.zoom': 'Acerca el mapa para ver vuelos', 'status.replay': 'Reproducción',
    'list.title': 'Vuelos visibles', 'list.sort': 'Ordenar por', 'list.sort.alt': 'Altitud', 'list.sort.spd': 'Velocidad', 'list.sort.cs': 'Callsign',
    'list.empty': 'No hay vuelos con estos filtros en la vista actual',
    'filters.title': 'Filtros', 'filters.hideGround': 'Ocultar aviones en tierra', 'filters.military': 'Solo militares',
    'filters.type': 'Tipo de aeronave', 'filters.all': 'Todos', 'filters.plane': 'Aviones', 'filters.light': 'Aviación ligera', 'filters.heli': 'Helicópteros',
    'filters.alt': 'Altitud', 'filters.alt.low': 'Baja (< 3 km)', 'filters.alt.mid': 'Media (3–9 km)', 'filters.alt.high': 'Alta (> 9 km)',
    'filters.text': 'Callsign o matrícula empieza por', 'filters.reset': 'Quitar filtros',
    'layers.title': 'Capas', 'layers.trails': 'Estelas de los aviones', 'layers.airports': 'Aeropuertos', 'layers.rain': 'Radar de lluvia',
    'layers.legend': 'Color por altitud', 'layers.ground': 'En tierra',
    'watch.title': 'Seguimiento y alertas', 'watch.kind': 'Tipo', 'watch.registration': 'Matrícula', 'watch.value': 'Valor', 'watch.label': 'Nota (opcional)',
    'watch.add': 'Vigilar', 'watch.hint': 'Las emergencias (squawk 7500, 7600 y 7700) siempre se vigilan.',
    'watch.notify': 'Activar avisos del navegador', 'watch.list': 'Vigilados', 'watch.alerts': 'Alertas recientes',
    'watch.empty': 'Nada vigilado todavía', 'watch.noalerts': 'Sin alertas', 'watch.remove': 'Quitar', 'watch.token': 'Token de administrador',
    'watch.added': 'Añadido a la lista de seguimiento', 'watch.denied': 'Notificaciones bloqueadas por el navegador',
    'stats.title': 'Estadísticas', 'stats.period': 'Periodo', 'stats.6h': 'Últimas 6 h', 'stats.24h': 'Últimas 24 h', 'stats.72h': 'Últimos 3 días', 'stats.168h': 'Últimos 7 días',
    'stats.perhour': 'Vuelos distintos por hora', 'stats.airlines': 'Aerolíneas más frecuentes', 'stats.altitude': 'Distribución de altitudes',
    'stats.empty': 'Aún no hay datos grabados', 'stats.zone': 'Datos de las zonas que se están grabando',
    'settings.title': 'Ajustes', 'settings.theme': 'Tema', 'settings.theme.auto': 'Automático', 'settings.theme.light': 'Claro', 'settings.theme.dark': 'Oscuro',
    'settings.units': 'Unidades', 'settings.units.aviation': 'Aviación (ft, kt)', 'settings.units.metric': 'Métricas (m, km/h)', 'settings.lang': 'Idioma',
    'settings.install': 'Instalar aplicación', 'settings.shortcuts': 'Atajos', 'settings.sc.search': 'buscar', 'settings.sc.close': 'cerrar',
    'settings.sc.follow': 'seguir vuelo', 'settings.credits': 'Fuentes de datos',
    'replay.time': 'Instante', 'replay.speed': 'Velocidad', 'replay.live': 'Volver al vivo', 'replay.empty': 'Todavía no hay historial grabado', 'replay.nodata': 'sin datos grabados aquí',
    'card.ground': 'En tierra', 'card.airborne': 'En vuelo', 'card.nosignal': 'Sin señal', 'card.military': 'Militar',
    'card.emergency': 'Emergencia', 'card.alt': 'Altitud (nivel del mar)', 'card.agl': 'Sobre el terreno', 'card.speed': 'Velocidad', 'card.heading': 'Rumbo', 'card.vrate': 'Vel. vertical',
    'card.reg': 'Matrícula', 'card.aircraft': 'Aeronave', 'card.operator': 'Operador', 'card.squawk': 'Squawk', 'card.position': 'Posición', 'card.routenote': 'Ruta aproximada (datos abiertos, puede estar desactualizada)',
    'card.follow': 'Seguir', 'card.watch': 'Vigilar', 'card.share': 'Compartir', 'card.close': 'Cerrar',
    'airport.weather': 'Clima', 'airport.ground': 'En tierra', 'airport.near': 'En el aire cerca', 'airport.arriving': 'Llegando', 'airport.departing': 'Saliendo',
    'airport.none': 'Ninguno detectado', 'airport.elevation': 'Elevación', 'airport.wind': 'Viento', 'toast.source': 'Las fuentes de datos no responden, reintentando',
    'layers.sigmet': 'Zonas peligrosas (SIGMET)',
    'status.src': 'Fuente', 'status.credits': 'créditos OpenSky', 'status.slow': 'actualizando más despacio para cuidar la cuota',
    'card.chase': 'Vista 3D', 'chase.exit': 'Salir de la vista 3D',
    'special.title': 'Aeronaves especiales', 'special.empty': 'Ninguna a la vista ahora', 'special.hint': 'Emergencias, militares, aeronaves de interés y tipos poco comunes (A380, Antonov, Beluga…).',
    'special.notify': 'Avisarme cuando aparezca una', 'special.emergency': 'Emergencia', 'special.military': 'Militar', 'special.interesting': 'De interés', 'special.rare': 'Poco común',
    'special.appeared': 'Aeronave especial a la vista',
    'card.progress': 'Progreso del vuelo', 'card.remaining': 'faltan', 'card.eta': 'llegada en', 'card.wind': 'Viento en vuelo', 'card.tas': 'Vel. aerodinámica',
    'card.headwind': 'de cara', 'card.tailwind': 'de cola', 'card.crosswind': 'cruzado', 'card.interesting': 'De interés',
    'airport.metar': 'Parte meteorológico (METAR)', 'airport.taf': 'Pronóstico (TAF)', 'airport.runway': 'Pista en uso', 'airport.runways': 'Pistas',
    'airport.atc': 'Buscar audio en vivo (LiveATC)', 'airport.atc.hint': 'LiveATC no cubre todos los aeropuertos; si el tuyo no aparece, no hay audio público allí.',
    'airport.freq': 'Frecuencias de radio (MHz)', 'airport.freq.hint': 'Datos de OurAirports: pueden estar incompletos.', 'airport.vis': 'Visibilidad', 'airport.clouds': 'Nubes', 'airport.qnh': 'QNH', 'airport.nometar': 'Sin METAR para este aeropuerto',
    'stats.records': 'Récords de tu cielo', 'stats.rec.alt': 'Más alto', 'stats.rec.spd': 'Más rápido', 'stats.rec.type': 'Tipo más visto', 'stats.rec.peak': 'Hora pico', 'stats.rec.total': 'Aeronaves distintas',
    'watch.locked': 'La lista es privada: añade algo para introducir el token',
    'tool.special': 'Aeronaves especiales',
    'offline': 'Sin conexión',
};

const en = {
    'search.placeholder': 'Search flight, registration or airport', 'search.none': 'No results',
    'toolbar.label': 'Tools', 'tool.menu': 'Tools',
    'tool.locate': 'My location', 'tool.list': 'Visible flights', 'tool.filters': 'Filters', 'tool.layers': 'Layers',
    'tool.replay': 'Historical replay', 'tool.stats': 'Statistics', 'tool.watch': 'Watchlist and alerts', 'tool.settings': 'Settings',
    'common.close': 'Close', 'common.copied': 'Link copied', 'common.error': 'Something went wrong',
    'status.connecting': 'Connecting…', 'status.live': 'Live', 'status.flights': '{n} flights', 'status.reconnecting': 'Reconnecting…',
    'status.zoom': 'Zoom in to see flights', 'status.replay': 'Replay',
    'list.title': 'Visible flights', 'list.sort': 'Sort by', 'list.sort.alt': 'Altitude', 'list.sort.spd': 'Speed', 'list.sort.cs': 'Callsign',
    'list.empty': 'No flights match these filters in the current view',
    'filters.title': 'Filters', 'filters.hideGround': 'Hide aircraft on the ground', 'filters.military': 'Military only',
    'filters.type': 'Aircraft type', 'filters.all': 'All', 'filters.plane': 'Airplanes', 'filters.light': 'Light aviation', 'filters.heli': 'Helicopters',
    'filters.alt': 'Altitude', 'filters.alt.low': 'Low (< 3 km)', 'filters.alt.mid': 'Medium (3–9 km)', 'filters.alt.high': 'High (> 9 km)',
    'filters.text': 'Callsign or registration starts with', 'filters.reset': 'Clear filters',
    'layers.title': 'Layers', 'layers.trails': 'Aircraft trails', 'layers.airports': 'Airports', 'layers.rain': 'Rain radar',
    'layers.legend': 'Color by altitude', 'layers.ground': 'On the ground',
    'watch.title': 'Watchlist and alerts', 'watch.kind': 'Type', 'watch.registration': 'Registration', 'watch.value': 'Value', 'watch.label': 'Note (optional)',
    'watch.add': 'Watch', 'watch.hint': 'Emergencies (squawk 7500, 7600 and 7700) are always watched.',
    'watch.notify': 'Enable browser notifications', 'watch.list': 'Watched', 'watch.alerts': 'Recent alerts',
    'watch.empty': 'Nothing watched yet', 'watch.noalerts': 'No alerts', 'watch.remove': 'Remove', 'watch.token': 'Admin token',
    'watch.added': 'Added to the watchlist', 'watch.denied': 'Notifications blocked by the browser',
    'stats.title': 'Statistics', 'stats.period': 'Period', 'stats.6h': 'Last 6 h', 'stats.24h': 'Last 24 h', 'stats.72h': 'Last 3 days', 'stats.168h': 'Last 7 days',
    'stats.perhour': 'Distinct flights per hour', 'stats.airlines': 'Most frequent airlines', 'stats.altitude': 'Altitude distribution',
    'stats.empty': 'No recorded data yet', 'stats.zone': 'Data from the zones being recorded',
    'settings.title': 'Settings', 'settings.theme': 'Theme', 'settings.theme.auto': 'Automatic', 'settings.theme.light': 'Light', 'settings.theme.dark': 'Dark',
    'settings.units': 'Units', 'settings.units.aviation': 'Aviation (ft, kt)', 'settings.units.metric': 'Metric (m, km/h)', 'settings.lang': 'Language',
    'settings.install': 'Install app', 'settings.shortcuts': 'Shortcuts', 'settings.sc.search': 'search', 'settings.sc.close': 'close',
    'settings.sc.follow': 'follow flight', 'settings.credits': 'Data sources',
    'replay.time': 'Time', 'replay.speed': 'Speed', 'replay.live': 'Back to live', 'replay.empty': 'No recorded history yet', 'replay.nodata': 'no data recorded here',
    'card.ground': 'On the ground', 'card.airborne': 'Airborne', 'card.nosignal': 'No signal', 'card.military': 'Military',
    'card.emergency': 'Emergency', 'card.alt': 'Altitude (sea level)', 'card.agl': 'Above ground', 'card.speed': 'Speed', 'card.heading': 'Heading', 'card.vrate': 'Vertical rate',
    'card.reg': 'Registration', 'card.aircraft': 'Aircraft', 'card.operator': 'Operator', 'card.squawk': 'Squawk', 'card.position': 'Position', 'card.routenote': 'Approximate route (open data, may be outdated)',
    'card.follow': 'Follow', 'card.watch': 'Watch', 'card.share': 'Share', 'card.close': 'Close',
    'airport.weather': 'Weather', 'airport.ground': 'On the ground', 'airport.near': 'Airborne nearby', 'airport.arriving': 'Arriving', 'airport.departing': 'Departing',
    'airport.none': 'None detected', 'airport.elevation': 'Elevation', 'airport.wind': 'Wind', 'toast.source': 'Data sources are not responding, retrying',
    'layers.sigmet': 'Hazard areas (SIGMET)',
    'status.src': 'Source', 'status.credits': 'OpenSky credits', 'status.slow': 'updating more slowly to save quota',
    'card.chase': '3D view', 'chase.exit': 'Exit 3D view',
    'special.title': 'Special aircraft', 'special.empty': 'None in view right now', 'special.hint': 'Emergencies, military, aircraft of interest and uncommon types (A380, Antonov, Beluga…).',
    'special.notify': 'Notify me when one appears', 'special.emergency': 'Emergency', 'special.military': 'Military', 'special.interesting': 'Of interest', 'special.rare': 'Uncommon',
    'special.appeared': 'Special aircraft in view',
    'card.progress': 'Flight progress', 'card.remaining': 'left', 'card.eta': 'arriving in', 'card.wind': 'Wind at altitude', 'card.tas': 'Airspeed',
    'card.headwind': 'headwind', 'card.tailwind': 'tailwind', 'card.crosswind': 'crosswind', 'card.interesting': 'Of interest',
    'airport.metar': 'Weather report (METAR)', 'airport.taf': 'Forecast (TAF)', 'airport.runway': 'Runway in use', 'airport.runways': 'Runways',
    'airport.atc': 'Find live audio (LiveATC)', 'airport.atc.hint': 'LiveATC does not cover every airport; if yours is missing, there is no public audio there.',
    'airport.freq': 'Radio frequencies (MHz)', 'airport.freq.hint': 'Data from OurAirports: may be incomplete.', 'airport.vis': 'Visibility', 'airport.clouds': 'Clouds', 'airport.qnh': 'QNH', 'airport.nometar': 'No METAR for this airport',
    'stats.records': 'Records of your sky', 'stats.rec.alt': 'Highest', 'stats.rec.spd': 'Fastest', 'stats.rec.type': 'Most seen type', 'stats.rec.peak': 'Peak hour', 'stats.rec.total': 'Distinct aircraft',
    'watch.locked': 'The list is private: add something to enter the token',
    'tool.special': 'Special aircraft',
    'offline': 'Offline',
};

const dictionaries = { es, en };

export function t(key, vars = {}) {
    const text = dictionaries[state.lang]?.[key] ?? es[key] ?? key;
    return text.replace(/\{(\w+)\}/g, (_, name) => vars[name] ?? '');
}

/** Traduce todo lo marcado con data-i18n* dentro de `root`. */
export function applyI18n(root = document) {
    document.documentElement.lang = state.lang;
    for (const el of $$('[data-i18n]', root)) el.textContent = t(el.dataset.i18n);
    for (const [attr, target] of [['i18nPlaceholder', 'placeholder'], ['i18nAria', 'aria-label'], ['i18nTitle', 'title']]) {
        for (const el of $$(`[data-${attr.replace(/[A-Z]/g, c => '-' + c.toLowerCase())}]`, root)) el.setAttribute(target, t(el.dataset[attr]));
    }
}
