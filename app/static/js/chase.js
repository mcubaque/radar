// Vista 3D en primera persona: la cámara va detrás del avión seleccionado, a su altura, sobre el relieve y la imagen
// satelital. El avión es un modelo 3D según su tipo, dibujado por una capa WebGL propia (MapLibre no trae modelos 3D),
// y las pistas de los aeropuertos cercanos se dibujan sobre el terreno.
import { FAMILY_LENGTH_M, FLOATS_PER_VERTEX, aircraftMesh, familyFor, liveryColor } from './aircraftmesh.js';
import { currentPosition, flights } from './flightlayer.js';
import { MAX_AGL_ALT_M, altitudeBucket, bucketColor, heightAboveGround } from './flightmodel.js';
import { map, onStyleReady } from './map.js';
import { RUNWAY_FLOATS_PER_VERTEX, runwayMesh } from './runwaymesh.js';
import { on, state } from './state.js';
import { followZone, syncViewport } from './stream.js';
import * as units from './units.js';
import { $, fetchJson } from './util.js';
import { HORIZON_COLOR, TERRAIN_EXAGGERATION, setTerrain } from './weather.js';

const PITCH = 76;        // cámara algo por encima del avión, mirando hacia delante y un poco hacia abajo
const BASE_ZOOM = 19.6;  // con un avión de 38 m, la cámara queda a unos 200 m; los modelos más chicos acercan la cámara
const REFERENCE_LENGTH_M = FAMILY_LENGTH_M.narrow;
const HEADING_TAU_S = 0.8;     // constantes de tiempo de los filtros que quitan el temblor (independientes de los fps)
const POSITION_TAU_S = 1.5;
const ALTITUDE_TAU_S = 0.6;
const GROUND_TAU_S = 0.8;
const ZONE_EVERY_MS = 3000;
const HUD_EVERY_MS = 500;
const REFERENCE_EVERY_MS = 60000;
const RUNWAYS_MOVE_DEG = 0.15;  // se piden pistas de nuevo al alejarse tanto del último punto consultado
const TERRAIN_AGREE_M = 40;     // diferencia máxima entre el terreno medido y la elevación oficial del aeropuerto
const FT_M = 0.3048;
const RUNWAY_LIFT_M = 3;        // la pista flota apenas sobre el terreno para no quedar tapada por su ruido
const SETTLE_EVERY_MS = 1000;
const BLEND_ALT_M = 2000;       // tramo en el que la altura sobre el terreno cede ante la altitud barométrica
const INTERACTIONS = ['dragPan', 'scrollZoom', 'touchZoomRotate', 'touchPitch', 'dragRotate', 'keyboard', 'doubleClickZoom', 'boxZoom'];
const HIDDEN_LAYERS = ['halo', 'trails', 'track'];

let frame = null;
let chaseId = null;
let lastZone = 0;
let lastHud = 0;
let lastSettle = 0;
let surface = { at: 0, hpa: null };       // presión en superficie bajo el avión: da la altura real sobre el suelo
let runwaysAt = null;                     // [lat, lon] de la última consulta de pistas
let runways = [];                         // {mesh, ends, official, z, buffer}: pistas cercanas; z es su altura fija
let last = null;  // {at, target: [lat, lon], ground} del fotograma anterior; null al empezar
const model = { lat: 0, lon: 0, heading: 0, altitude: 0, family: 'narrow', accent: '#2f80ed', meshKey: null };

// --- capa WebGL: dibuja la malla del avión con la matriz de MapLibre (coordenadas Mercator) ---

const VERTEX = `
attribute vec3 a_pos; attribute vec3 a_normal; attribute vec3 a_color;
uniform mat4 u_matrix; uniform vec2 u_rot;
varying vec3 v_color; varying vec3 v_normal;
void main() {
    gl_Position = u_matrix * vec4(a_pos, 1.0);
    v_color = a_color;
    v_normal = vec3(u_rot.x * a_normal.x + u_rot.y * a_normal.y, -u_rot.y * a_normal.x + u_rot.x * a_normal.y, a_normal.z);
}`;
const FRAGMENT = `
precision mediump float;
varying vec3 v_color; varying vec3 v_normal;
void main() {
    float light = 0.45 + 0.55 * max(dot(normalize(v_normal), normalize(vec3(0.5, 0.3, 0.8))), 0.0);
    gl_FragColor = vec4(v_color * light, 1.0);
}`;

function compile(gl, type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader));
    return shader;
}

/** Producto de matrices 4×4 en orden de columnas (el de WebGL). */
function multiply(a, b) {
    const out = new Float32Array(16);
    for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) {
        out[c * 4 + r] = a[r] * b[c * 4] + a[4 + r] * b[c * 4 + 1] + a[8 + r] * b[c * 4 + 2] + a[12 + r] * b[c * 4 + 3];
    }
    return out;
}

const aircraftLayer = {
    id: 'aircraft3d',
    type: 'custom',
    renderingMode: '3d',
    onAdd(_map, gl) {
        const program = gl.createProgram();
        gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, VERTEX));
        gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, FRAGMENT));
        gl.linkProgram(program);
        this.program = program;
        this.buffer = gl.createBuffer();
        this.vertices = 0;
        this.uploaded = null;
    },
    render(gl, args) {
        if (!state.chase) return;
        if (this.uploaded !== model.meshKey) {  // otro tipo de avión o de color: se vuelve a subir la malla
            const mesh = aircraftMesh(model.family, { accent: model.accent });
            gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
            gl.bufferData(gl.ARRAY_BUFFER, mesh, gl.STATIC_DRAW);
            this.vertices = mesh.length / FLOATS_PER_VERTEX;
            this.uploaded = model.meshKey;
        }
        const main = args.defaultProjectionData?.mainMatrix ?? args;
        const origin = maplibregl.MercatorCoordinate.fromLngLat([model.lon, model.lat], model.altitude);
        const scale = origin.meterInMercatorCoordinateUnits() * FAMILY_LENGTH_M[model.family];
        const h = model.heading * Math.PI / 180, cos = Math.cos(h), sin = Math.sin(h);
        // unidades del modelo (x este, y norte, z arriba) -> Mercator (y crece hacia el sur); el producto se hace en doble
        // precisión en JS, así la traslación que llega a la GPU es pequeña y el modelo no tiembla
        const toWorld = new Float32Array([
            scale * cos, scale * sin, 0, 0,
            scale * sin, -scale * cos, 0, 0,
            0, 0, scale, 0,
            origin.x, origin.y, origin.z, 1,
        ]);

        gl.useProgram(this.program);
        gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
        const stride = FLOATS_PER_VERTEX * 4;
        [['a_pos', 0], ['a_normal', 3], ['a_color', 6]].forEach(([name, offset]) => {
            const loc = gl.getAttribLocation(this.program, name);
            gl.enableVertexAttribArray(loc);
            gl.vertexAttribPointer(loc, 3, gl.FLOAT, false, stride, offset * 4);
        });
        gl.uniformMatrix4fv(gl.getUniformLocation(this.program, 'u_matrix'), false, multiply(main, toWorld));
        gl.uniform2f(gl.getUniformLocation(this.program, 'u_rot'), cos, sin);
        gl.enable(gl.DEPTH_TEST);
        gl.disable(gl.CULL_FACE);
        gl.drawArrays(gl.TRIANGLES, 0, this.vertices);
        for (const name of ['a_pos', 'a_normal', 'a_color']) gl.disableVertexAttribArray(gl.getAttribLocation(this.program, name));
    },
};

// --- pistas: superficie plana propia, a la altura del terreno medida a lo largo de ella ---
// Dibujarlas pegadas al relieve las hace ondular con el ruido del modelo de elevación; las pistas reales son planas.

const RUNWAY_VERTEX = `
attribute vec3 a_pos; attribute vec3 a_color;
uniform mat4 u_matrix;
varying vec3 v_color;
void main() { gl_Position = u_matrix * vec4(a_pos, 1.0); v_color = a_color; }`;
const RUNWAY_FRAGMENT = 'precision mediump float; varying vec3 v_color; void main() { gl_FragColor = vec4(v_color, 1.0); }';

const runwayLayer = {
    id: 'runways3d',
    type: 'custom',
    renderingMode: '3d',
    onAdd(_map, gl) {
        const program = gl.createProgram();
        gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, RUNWAY_VERTEX));
        gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, RUNWAY_FRAGMENT));
        gl.linkProgram(program);
        this.program = program;
    },
    render(gl, args) {
        if (!state.chase) return;
        const main = args.defaultProjectionData?.mainMatrix ?? args;
        gl.useProgram(this.program);
        const stride = RUNWAY_FLOATS_PER_VERTEX * 4;
        gl.enable(gl.DEPTH_TEST);
        gl.enable(gl.POLYGON_OFFSET_FILL);
        gl.polygonOffset(-2, -2);
        for (const rw of runways) {
            if (!rw.buffer) {
                rw.buffer = gl.createBuffer();
                gl.bindBuffer(gl.ARRAY_BUFFER, rw.buffer);
                gl.bufferData(gl.ARRAY_BUFFER, rw.mesh.vertices, gl.STATIC_DRAW);
            }
            const origin = maplibregl.MercatorCoordinate.fromLngLat([rw.mesh.lon, rw.mesh.lat], rw.z);
            const scale = origin.meterInMercatorCoordinateUnits();
            // metros locales (x este, y norte, z arriba) -> Mercator, con el origen en el centro de la pista
            const toWorld = new Float32Array([scale, 0, 0, 0, 0, -scale, 0, 0, 0, 0, scale, 0, origin.x, origin.y, origin.z, 1]);
            gl.bindBuffer(gl.ARRAY_BUFFER, rw.buffer);
            [['a_pos', 0], ['a_color', 3]].forEach(([name, offset]) => {
                const loc = gl.getAttribLocation(this.program, name);
                gl.enableVertexAttribArray(loc);
                gl.vertexAttribPointer(loc, 3, gl.FLOAT, false, stride, offset * 4);
            });
            gl.uniformMatrix4fv(gl.getUniformLocation(this.program, 'u_matrix'), false, multiply(main, toWorld));
            gl.drawArrays(gl.TRIANGLES, 0, rw.mesh.vertices.length / RUNWAY_FLOATS_PER_VERTEX);
            for (const name of ['a_pos', 'a_color']) gl.disableVertexAttribArray(gl.getAttribLocation(this.program, name));
        }
        gl.disable(gl.POLYGON_OFFSET_FILL);
    },
};

function addLayers() {
    try {
        map.addLayer(runwayLayer);
        map.addLayer(aircraftLayer);
    } catch (e) {  // sin WebGL suficiente la vista 3D no estará disponible, pero el resto del mapa debe seguir funcionando
        console.warn('Vista 3D no disponible:', e.message);
    }
}

async function refreshRunways(lat, lon) {
    runwaysAt = [lat, lon];
    const airports = await fetchJson(`/api/runways?lat=${lat}&lon=${lon}`).catch(() => []);
    if (!state.chase) return;
    runways = airports.flatMap(a => a.runways.map(ends => {
        const official = (a.elevation_ft ?? 0) * FT_M * TERRAIN_EXAGGERATION;
        // parte de la elevación oficial del aeropuerto; settleRunways la ajusta al relieve que se ve dibujado
        return { mesh: runwayMesh(ends), ends, official, z: official + RUNWAY_LIFT_M, buffer: null };
    }));
}

/**
 * Mantiene la altura fija de cada pista sobre el relieve que se ve dibujado: un percentil alto de la elevación medida a lo
 * largo de su eje, para que el ruido del modelo de elevación no la entierre. Se repite porque al acercarse MapLibre carga
 * teselas más finas que cambian unos metros el relieve. Antes de cargar devuelve 0: esa medida no se acepta si se aparta más
 * de TERRAIN_AGREE_M de la elevación oficial del aeropuerto (con la que arranca la pista).
 */
function settleRunways() {
    if (Date.now() - lastSettle < SETTLE_EVERY_MS) return;
    lastSettle = Date.now();
    for (const rw of runways) {
        const { le_lat: lat0, le_lon: lon0, he_lat: lat1, he_lon: lon1 } = rw.ends;
        const along = i => [lon0 + ((lon1 - lon0) * i) / 8, lat0 + ((lat1 - lat0) * i) / 8];
        const heights = Array.from({ length: 9 }, (_, i) => map.queryTerrainElevation(along(i)))
            .filter(h => h != null).sort((a, b) => a - b);
        if (heights.length < 6) continue;
        const high = heights[Math.floor(heights.length * 0.8)];
        if (Math.abs(high - rw.official) < TERRAIN_AGREE_M) rw.z = high + RUNWAY_LIFT_M;
    }
}

async function refreshSurface(lat, lon) {
    surface.at = Date.now();  // también tras un fallo, para no insistir
    const { surface_hpa: hpa } = await fetchJson(`/api/reference?lat=${lat}&lon=${lon}`).catch(() => ({}));
    if (hpa) surface.hpa = hpa;
}

// --- altura del avión ---

/**
 * Altura del modelo en la escala del relieve exagerado. Con presión de superficie conocida se usa la altura real sobre el
 * suelo (la altitud barométrica sola puede errar cien metros y hundir el avión en la pista); por encima de
 * MAX_AGL_ALT_M se usa la altitud barométrica y entre medias se mezclan para que la cámara no dé saltos.
 */
function modelAltitude(rec, ground) {
    if (rec.gnd || rec.alt == null) return ground;
    const baro = rec.alt + (rec.vr ?? 0) * Math.min((Date.now() - rec.t0) / 1000, 30);  // entre dos lecturas sigue la subida o bajada
    const high = baro * TERRAIN_EXAGGERATION;
    if (!surface.hpa || baro >= MAX_AGL_ALT_M) return high;
    const low = ground + heightAboveGround(baro, surface.hpa);
    const weight = Math.min(1, (MAX_AGL_ALT_M - baro) / BLEND_ALT_M);
    return weight * low + (1 - weight) * high;
}

// --- cámara ---

const hud = () => $('#chase-hud');
const angleDiff = (to, from) => ((to - from + 540) % 360) - 180;

function showHud(rec) {
    hud().textContent = [rec.cs || rec.id, rec.ty, units.altitude(rec.alt)[0], units.speed(rec.spd)[0], units.heading(rec.hdg)].filter(Boolean).join(' · ');
}

/**
 * Acerca `value` a `target` con un filtro exponencial de constante `tau`. Lo que cambia de golpe en los datos (una lectura
 * nueva, una tesela de relieve que carga) se reparte en el tiempo en vez de verse como un salto o un temblor.
 */
const approach = (value, target, dt, tau) => target + (value - target) * Math.exp(-dt / tau);

function step() {
    const rec = flights.get(chaseId);
    if (!rec) return stopChase();
    const now = Date.now();
    const dt = last ? Math.min((now - last.at) / 1000, 0.25) : 0;
    const [targetLat, targetLon] = currentPosition(rec);
    const groundNow = map.queryTerrainElevation([targetLon, targetLat]) ?? 0;  // el relieve ya viene exagerado
    if (last) {
        // la posición avanza con la estimación y solo el error acumulado se corrige despacio: sin retraso ni saltos
        model.lat = approach(model.lat + (targetLat - last.target[0]), targetLat, dt, POSITION_TAU_S);
        model.lon = approach(model.lon + (targetLon - last.target[1]), targetLon, dt, POSITION_TAU_S);
        last.ground = approach(last.ground, groundNow, dt, GROUND_TAU_S);
        model.heading = (model.heading + angleDiff(rec.hdg ?? model.heading, model.heading) * (1 - Math.exp(-dt / HEADING_TAU_S)) + 360) % 360;
    } else {
        model.lat = targetLat;
        model.lon = targetLon;
        last = { ground: groundNow };
    }
    last.at = now;
    last.target = [targetLat, targetLon];
    const altitude = modelAltitude(rec, last.ground);
    model.altitude = dt ? approach(model.altitude, altitude, dt, ALTITUDE_TAU_S) : altitude;
    const { lat, lon } = model;
    if (Date.now() - surface.at > REFERENCE_EVERY_MS) refreshSurface(lat, lon);
    if (!runwaysAt || Math.max(Math.abs(lat - runwaysAt[0]), Math.abs(lon - runwaysAt[1])) > RUNWAYS_MOVE_DEG) refreshRunways(lat, lon);
    settleRunways();
    if (Date.now() - lastHud > HUD_EVERY_MS) {
        showHud(rec);
        lastHud = Date.now();
    }
    const zoom = BASE_ZOOM + Math.log2(REFERENCE_LENGTH_M / FAMILY_LENGTH_M[model.family]);  // el modelo se ve igual de grande
    map.jumpTo({ center: [lon, lat], bearing: model.heading, pitch: PITCH, zoom, elevation: model.altitude });
    if (Date.now() - lastZone > ZONE_EVERY_MS) {
        followZone(lat, lon);
        lastZone = Date.now();
    }
    frame = requestAnimationFrame(step);
}

/** Familia y color de cola del vuelo; si cambian se reconstruye la malla. */
function pickModel(rec) {
    model.family = familyFor(rec);
    model.accent = liveryColor(rec.cs) ?? bucketColor(altitudeBucket(rec));
    model.meshKey = `${model.family}${model.accent}`;
}

export function startChase(id) {
    const rec = flights.get(id);
    if (!rec || state.chase || !map.getLayer('aircraft3d')) return;
    chaseId = id;
    model.heading = rec.hdg ?? 0;
    pickModel(rec);
    state.chase = true;
    setTerrain(true);
    map.getContainer().style.backgroundColor = HORIZON_COLOR;  // detrás de las teselas lejanas, sin franja oscura
    map.setMaxPitch(85);
    map.setCenterClampedToGround(false);
    for (const handler of INTERACTIONS) map[handler].disable();
    map.setPadding({ top: Math.round(innerHeight * 0.3), bottom: 0, left: 0, right: 0 });  // el avión queda en la parte baja
    for (const layer of HIDDEN_LAYERS) map.getLayer(layer) && map.setLayoutProperty(layer, 'visibility', 'none');
    map.setPaintProperty('planes', 'icon-opacity', 0.3);
    document.body.classList.add('chase');
    lastZone = 0;
    surface = { at: 0, hpa: null };
    runwaysAt = null;
    runways = [];
    last = null;
    frame = requestAnimationFrame(step);
}

export function stopChase() {
    if (!state.chase) return;
    cancelAnimationFrame(frame);
    state.chase = false;
    const rec = flights.get(chaseId);
    chaseId = null;
    for (const handler of INTERACTIONS) map[handler].enable();
    map.setCenterClampedToGround(true);
    setTerrain(false);
    map.getContainer().style.backgroundColor = '';
    runways = [];
    for (const layer of HIDDEN_LAYERS) map.getLayer(layer) && map.setLayoutProperty(layer, 'visibility', 'visible');
    map.setPaintProperty('planes', 'icon-opacity', 1);
    map.setMaxPitch(0);
    map.setPadding({ top: 0, bottom: 0, left: 0, right: 0 });
    document.body.classList.remove('chase');
    map.jumpTo({ elevation: 0 });
    map.easeTo({ pitch: 0, bearing: 0, zoom: 11, ...(rec && { center: [rec.pos[1], rec.pos[0]] }), duration: 700 });
    syncViewport();
}

export function bindChase() {
    onStyleReady(addLayers);
    $('#chase-exit').addEventListener('click', stopChase);
    on('select', () => state.chase && state.selected !== chaseId && stopChase());
}
