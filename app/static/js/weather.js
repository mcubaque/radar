// Capas de información aeronáutica y de terreno: SIGMET, relieve 3D (solo en la vista en primera persona) y pistas.
import { runwayLine } from './flightmodel.js';
import { map, onStyleReady } from './map.js';
import { on, state } from './state.js';
import { fetchJson } from './util.js';

const empty = { type: 'FeatureCollection', features: [] };
const below = () => (map.getLayer('trails') ? 'trails' : undefined);

// --- SIGMET: tormentas, turbulencia, hielo, ceniza volcánica ---

const HAZARD_COLORS = {
    TS: '#ef4444', TURB: '#f97316', ICE: '#38bdf8', VA: '#a16207', TC: '#a855f7', MTW: '#eab308',
};
const FALLBACK_COLOR = '#94a3b8';
const hazardColor = ['match', ['get', 'hazard'], ...Object.entries(HAZARD_COLORS).flat(), FALLBACK_COLOR];

async function applySigmet() {
    for (const id of ['sigmet-line', 'sigmet-fill']) if (map.getLayer(id)) map.removeLayer(id);
    if (map.getSource('sigmet')) map.removeSource('sigmet');
    if (!state.layers.sigmet) return;
    const data = await fetchJson('/api/sigmets').catch(() => empty);
    if (!state.layers.sigmet || map.getSource('sigmet')) return;  // se apagó o se adelantó otra llamada
    map.addSource('sigmet', { type: 'geojson', data });
    map.addLayer({ id: 'sigmet-fill', type: 'fill', source: 'sigmet', paint: { 'fill-color': hazardColor, 'fill-opacity': 0.16 } }, below());
    map.addLayer({ id: 'sigmet-line', type: 'line', source: 'sigmet', paint: { 'line-color': hazardColor, 'line-width': 1.5, 'line-dasharray': [2, 2] } }, below());
}

const has = value => value != null && value !== 'null';

function showSigmetPopup(e) {
    if (!map.getLayer('sigmet-fill') || map.queryRenderedFeatures(e.point, { layers: ['planes'] }).length) return;
    const p = map.queryRenderedFeatures(e.point, { layers: ['sigmet-fill'] })[0]?.properties;
    if (!p) return;
    const box = document.createElement('div');
    const title = document.createElement('b');
    title.textContent = `${p.hazard}${has(p.name) ? ' · ' + p.name : ''}`;
    const body = document.createElement('div');
    const top = has(p.top_ft) ? `FL${Math.round(p.top_ft / 100)}` : '—';
    const until = has(p.valid_to)
        ? new Date(p.valid_to * 1000).toLocaleTimeString(state.lang, { hour: '2-digit', minute: '2-digit' }) : '—';
    body.textContent = `${top} · ≤ ${until}`;
    box.append(title, body);
    new maplibregl.Popup({ closeButton: false, maxWidth: '240px' }).setLngLat(e.lngLat).setDOMContent(box).addTo(map);
}

// --- relieve 3D (teselas de elevación abiertas de AWS, formato Terrarium) ---

export const TERRAIN_EXAGGERATION = 1.3;
let terrainOn = false;

const DEM_TILES = ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'];
// Sentinel-2 sin nubes de EOX (CC BY 4.0): imagen satelital del suelo
const SATELLITE_TILES = ['https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg'];
export const HORIZON_COLOR = '#dbe8f5';
const SKY = {
    'sky-color': '#5b9bd5', 'horizon-color': HORIZON_COLOR, 'fog-color': HORIZON_COLOR,
    'sky-horizon-blend': 0.6, 'horizon-fog-blend': 0.7, 'fog-ground-blend': 0.35,
};

function applyTerrain() {
    for (const id of ['hillshade', 'satellite']) if (map.getLayer(id)) map.removeLayer(id);
    for (const id of ['terrain', 'terrain-shade', 'satellite']) if (map.getSource(id)) {
        if (id === 'terrain') map.setTerrain(null);
        map.removeSource(id);
    }
    map.setSky(terrainOn ? SKY : undefined);
    if (!terrainOn) return;
    const dem = { type: 'raster-dem', encoding: 'terrarium', tileSize: 256, maxzoom: 14, tiles: DEM_TILES };
    map.addSource('terrain', { ...dem, attribution: 'Relieve: Mapzen / AWS Terrain Tiles' });
    map.addSource('terrain-shade', dem);  // fuente aparte para el sombreado: MapLibre lo recomienda
    map.addSource('satellite', {
        type: 'raster', tileSize: 256, maxzoom: 14, tiles: SATELLITE_TILES,
        attribution: '<a href="https://s2maps.eu" target="_blank" rel="noopener">Sentinel-2 cloudless</a> by EOX IT Services GmbH (contiene datos Copernicus Sentinel modificados 2016)',
    });
    map.addLayer({ id: 'satellite', type: 'raster', source: 'satellite', paint: { 'raster-fade-duration': 0 } }, below());
    map.addLayer({ id: 'hillshade', type: 'hillshade', source: 'terrain-shade', paint: { 'hillshade-exaggeration': 0.35 } }, below());
    map.setTerrain({ source: 'terrain', exaggeration: TERRAIN_EXAGGERATION });
}

export function setTerrain(on) {
    terrainOn = on;
    applyTerrain();
}

// --- pistas del aeropuerto abierto ---

let runwayData = { runways: [], inUse: null };

function drawRunways() {
    const source = map.getSource('runways');
    if (!source) return;
    const { runways, inUse } = runwayData;
    source.setData({
        type: 'FeatureCollection',
        features: runways.map(rw => ({
            type: 'Feature', geometry: { type: 'LineString', coordinates: runwayLine(rw) },
            properties: { active: rw.le_ident === inUse || rw.he_ident === inUse ? 1 : 0 },
        })),
    });
}

function applyRunways() {
    map.addSource('runways', { type: 'geojson', data: empty });
    map.addLayer({
        id: 'runways', type: 'line', source: 'runways',
        paint: {
            'line-color': ['case', ['==', ['get', 'active'], 1], '#22c55e', '#94a3b8'],
            'line-width': ['interpolate', ['linear'], ['zoom'], 9, 2, 14, 8],
        },
    }, 'planes');
    drawRunways();
}

/** Dibuja las pistas de un aeropuerto, resaltando la que se deduce en uso; sin argumentos las borra. */
export function setRunways(runways = [], inUse = null) {
    runwayData = { runways, inUse };
    drawRunways();
}

export function bindWeather() {
    onStyleReady(applySigmet);
    onStyleReady(applyTerrain);  // setStyle borra el relieve: se recrea si la vista 3D sigue activa
    onStyleReady(applyRunways);
    on('layers', name => {
        if (name === 'sigmet') applySigmet();
    });
    map.on('click', showSigmetPopup);
    map.on('mouseenter', 'sigmet-fill', () => (map.getCanvas().style.cursor = 'help'));
    map.on('mouseleave', 'sigmet-fill', () => (map.getCanvas().style.cursor = ''));
    setInterval(() => state.layers.sigmet && applySigmet(), 5 * 60 * 1000);
}
