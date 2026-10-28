// Capas opcionales: aeropuertos, radar de lluvia y anillos de alcance del receptor propio.
import { circlePolygon } from './flightmodel.js';
import { t } from './i18n.js';
import { bounds, map, onStyleReady } from './map.js';
import { debounce, fetchJson } from './util.js';
import { emit, on, state } from './state.js';
import { toast } from './toast.js';

// --- aeropuertos (marcadores HTML: no dependen de las fuentes del estilo del mapa) ---

const markers = new Map();

function clearAirports() {
    markers.forEach(m => m.remove());
    markers.clear();
}

async function refreshAirports() {
    if (!state.layers.airports || map.getZoom() < state.config.min_zoom) return clearAirports();
    const query = new URLSearchParams({ ...bounds(), z: map.getZoom().toFixed(1) });
    const airports = await fetchJson(`/api/airports?${query}`).catch(() => []);
    if (!state.layers.airports) return;  // se apagó mientras cargaba
    const keep = new Set(airports.map(a => a.ident));
    for (const [id, marker] of markers) {
        if (!keep.has(id)) { marker.remove(); markers.delete(id); }
    }
    for (const a of airports) {
        if (markers.has(a.ident)) continue;
        const el = document.createElement('button');
        el.className = 'ap';
        el.type = 'button';
        el.textContent = a.iata || a.icao;
        el.title = a.name;
        el.addEventListener('click', e => { e.stopPropagation(); emit('pick-airport', a); });
        markers.set(a.ident, new maplibregl.Marker({ element: el }).setLngLat([a.lon, a.lat]).addTo(map));
    }
}
export const refreshAirportsSoon = debounce(refreshAirports, 400);

// --- radar de lluvia (RainViewer) ---

async function applyRain() {
    if (map.getLayer('rain')) map.removeLayer('rain');
    if (map.getSource('rain')) map.removeSource('rain');
    if (!state.layers.rain) return;
    const meta = await fetchJson('https://api.rainviewer.com/public/weather-maps.json').catch(() => null);
    const frame = meta?.radar?.past?.at(-1);
    if (!frame) return toast(t('common.error'), { type: 'error' });
    if (map.getSource('rain')) return;  // otra llamada se adelantó
    map.addSource('rain', {
        type: 'raster', tileSize: 256, maxzoom: 7, attribution: '<a href="https://www.rainviewer.com">RainViewer</a>',
        tiles: [`${meta.host}${frame.path}/256/{z}/{x}/{y}/2/1_1.png`],
    });
    map.addLayer({ id: 'rain', type: 'raster', source: 'rain', paint: { 'raster-opacity': 0.6 } }, map.getLayer('trails') ? 'trails' : undefined);
}

// --- anillos del receptor propio ---

function applyRings() {
    const r = state.config.receiver;
    if (!r) return;
    const features = [100, 200, 300].filter(km => km <= r.range_km).map(km => ({
        type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: circlePolygon(r.lat, r.lon, km) },
    }));
    map.addSource('rings', { type: 'geojson', data: { type: 'FeatureCollection', features } });
    map.addLayer({
        id: 'rings', type: 'line', source: 'rings',
        paint: { 'line-color': '#94a3b8', 'line-width': 1, 'line-dasharray': [3, 3], 'line-opacity': 0.7 },
    }, map.getLayer('trails') ? 'trails' : undefined);
}

export function bindExtras() {
    onStyleReady(applyRain);
    onStyleReady(applyRings);
    on('layers', name => {
        if (name === 'airports') refreshAirports();
        if (name === 'rain') applyRain();
    });
    setInterval(() => state.layers.rain && applyRain(), 10 * 60 * 1000);  // los cuadros del radar caducan
}
