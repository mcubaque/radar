// Vuelos en el mapa: iconos, capas WebGL, estelas, movimiento fluido y selección.
import * as model from './flightmodel.js';
import { map, onStyleReady } from './map.js';
import { emit, on, state } from './state.js';

const BLEND_MS = 2000; // tiempo en corregir hacia la posición real sin saltos
const TRAIL_POINTS = 30;
const TRAIL_MIN_STEP_DEG = 0.0005; // ~50 m: no se añaden puntos si casi no se movió
const FRAME_MS = 125;

export const flights = new Map(); // id -> vuelo con t0, from, blendStart, pos y trail
const empty = { type: 'FeatureCollection', features: [] };

// --- iconos ---

const PATHS = {
    plane: 'M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z',
    light: 'M12 2 13.2 8 22 9.5v2L13 11l-.4 8 2.9 1.5V22L12 21.2 8.5 22v-1.5L11.4 19 11 11 2 11.5v-2L10.8 8z',
};

function drawIcon(shape, color) {
    const size = 64;
    const canvas = Object.assign(document.createElement('canvas'), { width: size, height: size });
    const ctx = canvas.getContext('2d');
    ctx.scale(size / 24, size / 24);
    ctx.lineWidth = 1.1;
    ctx.lineJoin = 'round';
    ctx.strokeStyle = '#0b1220';
    ctx.fillStyle = color;
    if (shape === 'heli') {
        ctx.beginPath();
        ctx.ellipse(12, 11, 3.2, 5, 0, 0, Math.PI * 2);
        ctx.rect(11.3, 14, 1.4, 8);
        ctx.fill();
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(12, 11, 9, 0, Math.PI * 2);
        ctx.moveTo(3, 11); ctx.lineTo(21, 11);
        ctx.moveTo(12, 2); ctx.lineTo(12, 20);
        ctx.lineWidth = 0.9;
        ctx.stroke();
    } else {
        const path = new Path2D(PATHS[shape]);
        ctx.fill(path);
        ctx.stroke(path);
    }
    return ctx.getImageData(0, 0, size, size);
}

function registerIcons() {
    for (const shape of model.ICON_SHAPES) {
        for (let bucket = 0; bucket < model.ICON_BUCKETS; bucket++) {
            const name = `${shape}-${bucket}`;
            if (!map.hasImage(name)) map.addImage(name, drawIcon(shape, model.bucketColor(bucket)), { pixelRatio: 2 });
        }
    }
}

// --- capas ---

const haloFilter = () => ['any', ['==', ['get', 'em'], 1], ['==', ['get', 'id'], state.selected ?? '']];

function initLayers() {
    registerIcons();
    for (const id of ['flights', 'trails', 'track']) map.addSource(id, { type: 'geojson', data: empty });
    map.addLayer({
        id: 'trails', type: 'line', source: 'trails',
        layout: { 'line-cap': 'round', 'line-join': 'round', visibility: state.layers.trails ? 'visible' : 'none' },
        paint: { 'line-color': '#2f80ed', 'line-width': 1.5, 'line-opacity': 0.45 },
    });
    map.addLayer({
        id: 'track', type: 'line', source: 'track',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': '#ef4444', 'line-width': 2.5, 'line-opacity': 0.9 },
    });
    map.addLayer({
        id: 'halo', type: 'circle', source: 'flights', filter: haloFilter(),
        paint: {
            'circle-radius': 17, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-width': 3,
            'circle-stroke-color': ['case', ['==', ['get', 'em'], 1], '#ef4444', '#2563eb'],
        },
    });
    map.addLayer({
        id: 'planes', type: 'symbol', source: 'flights',
        layout: {
            'icon-image': ['get', 'icon'], 'icon-rotate': ['get', 'hdg'],
            'icon-rotation-alignment': 'map', 'icon-pitch-alignment': 'map',
            'icon-allow-overlap': true, 'icon-ignore-placement': true,
            'icon-size': ['interpolate', ['linear'], ['zoom'], 5, 0.55, 9, 0.8, 13, 1.1],
        },
    });
    redraw();
    drawTrails();
}

onStyleReady(initLayers);

export function bindPicking() {
    map.on('click', 'planes', e => {
        emit('pick', e.features[0].properties.id);
    });
    map.on('mouseenter', 'planes', () => (map.getCanvas().style.cursor = 'pointer'));
    map.on('mouseleave', 'planes', () => (map.getCanvas().style.cursor = ''));
}

let trackLine = [];  // [lon, lat] del trazo del vuelo seleccionado

const drawTrack = () =>
    map.getSource('track')?.setData(trackLine.length > 1
        ? { type: 'Feature', geometry: { type: 'LineString', coordinates: trackLine } }
        : empty);

export function setTrack(points) {
    trackLine = points.map(p => [p[1], p[0]]);
    drawTrack();
}

// --- datos ---

function upsert(f, now, previous) {
    const trail = previous?.trail || [];
    const last = trail[trail.length - 1];
    if (!last || Math.abs(last[0] - f.lon) + Math.abs(last[1] - f.lat) > TRAIL_MIN_STEP_DEG) {
        trail.push([f.lon, f.lat]);
        if (trail.length > TRAIL_POINTS) trail.shift();
    }
    flights.set(f.id, { ...f, t0: f.ts * 1000, blendStart: now, from: previous?.pos ?? null, pos: [f.lat, f.lon], trail });
}

/** Aplica un mensaje del stream: {full, flights, gone}. */
export function ingest(msg) {
    const now = Date.now();
    if (msg.full) {
        const keep = new Set(msg.flights.map(f => f.id));
        for (const id of flights.keys()) if (!keep.has(id)) flights.delete(id);
    }
    for (const id of msg.gone) flights.delete(id);
    for (const f of msg.flights) upsert(f, now, flights.get(f.id));
    const selected = flights.get(state.selected);
    const tip = trackLine[trackLine.length - 1];
    if (selected && tip && state.mode === 'live' && (tip[0] !== selected.lon || tip[1] !== selected.lat)) {
        trackLine.push([selected.lon, selected.lat]);  // el trazo avanza con el avión
        drawTrack();
    }
    drawTrails();
    emit('flights');
}

/** Reproducción histórica: reemplaza todo, sin estimar movimiento ni estelas. */
export function replaceAll(list) {
    flights.clear();
    for (const f of list) flights.set(f.id, { ...f, t0: f.ts * 1000, from: null, pos: [f.lat, f.lon], trail: [] });
    drawTrails();
    redraw();
    emit('flights');
}

function positionOf(rec, now) {
    const target = state.mode === 'live'
        ? model.advance(rec.lat, rec.lon, rec.gnd ? 0 : rec.spd, rec.hdg, (now - rec.t0) / 1000)
        : [rec.lat, rec.lon];
    if (rec.from) {
        const k = Math.min(1, (now - rec.blendStart) / BLEND_MS);
        if (k < 1) return [rec.from[0] + (target[0] - rec.from[0]) * k, rec.from[1] + (target[1] - rec.from[1]) * k];
        rec.from = null;
    }
    return target;
}

/** Posición estimada ahora de un vuelo (extrapolada y suavizada), [lat, lon]. */
export const currentPosition = rec => positionOf(rec, Date.now());

export const visibleFlights = () => [...flights.values()].filter(f => model.passes(f, state.filters));

export function redraw() {
    const source = map?.getSource('flights');
    if (!source) return;
    const now = Date.now();
    const features = [];
    for (const rec of flights.values()) {
        rec.pos = positionOf(rec, now);
        if (!model.passes(rec, state.filters)) continue;
        features.push({
            type: 'Feature',
            geometry: { type: 'Point', coordinates: [rec.pos[1], rec.pos[0]] },
            properties: { id: rec.id, icon: model.iconName(rec), hdg: rec.hdg ?? 0, em: rec.em ? 1 : 0 },
        });
    }
    source.setData({ type: 'FeatureCollection', features });
    const selected = flights.get(state.selected);
    if (state.follow && selected) map.jumpTo({ center: [selected.pos[1], selected.pos[0]] });
}

export function drawTrails() {
    const source = map?.getSource('trails');
    if (!source || !state.layers.trails) return;
    const features = visibleFlights()
        .filter(f => f.trail.length > 1)
        .map(f => ({ type: 'Feature', geometry: { type: 'LineString', coordinates: f.trail }, properties: {} }));
    source.setData({ type: 'FeatureCollection', features });
}

export function startAnimation() {
    let timer = setInterval(redraw, FRAME_MS);
    document.addEventListener('visibilitychange', () => {
        clearInterval(timer);
        if (!document.hidden) timer = setInterval(redraw, FRAME_MS);
    });
}

// --- reacciones al estado ---

on('select', () => map.getLayer('halo') && map.setFilter('halo', haloFilter()));
on('filters', () => { redraw(); drawTrails(); });
on('layers', () => {
    map.getLayer('trails') && map.setLayoutProperty('trails', 'visibility', state.layers.trails ? 'visible' : 'none');
    drawTrails();
});
