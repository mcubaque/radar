// Conexión en vivo (Server-Sent Events) con la zona visible del mapa.
import { ingest } from './flightlayer.js';
import { t } from './i18n.js';
import { bounds, map } from './map.js';
import { emit, state } from './state.js';
import { debounce } from './util.js';

const PAD = 0.3; // se pide una zona 30 % mayor para no reconectar a cada pequeño movimiento

let source = null;
let connected = null; // zona pedida actualmente
const statusListeners = [];
export const onStatus = fn => statusListeners.push(fn);
const setStatus = (kind, text) => statusListeners.forEach(fn => fn(kind, text));

const query = b => new URLSearchParams(b).toString();

function padded(b, factor) {
    const dLat = (b.lamax - b.lamin) * factor, dLon = (b.lomax - b.lomin) * factor;
    return {
        lamin: Math.max(-90, b.lamin - dLat), lomin: Math.max(-180, b.lomin - dLon),
        lamax: Math.min(90, b.lamax + dLat), lomax: Math.min(180, b.lomax + dLon),
    };
}

const contains = (outer, inner) =>
    outer && inner.lamin >= outer.lamin && inner.lamax <= outer.lamax && inner.lomin >= outer.lomin && inner.lomax <= outer.lomax;

export function stop() {
    source?.close();
    source = null;
    connected = null;
}

function connect(zone, fallback) {
    stop();
    connected = zone;
    source = new EventSource(`/api/stream?${query(zone)}`);
    source.addEventListener('flights', e => {
        const msg = JSON.parse(e.data);
        ingest(msg);
        if (msg.meta?.source) emit('meta', msg.meta);
        const down = msg.errors.length > 0 && msg.flights.length === 0;
        setStatus(down ? 'error' : 'ok', down ? t('toast.source') : null);
    });
    source.addEventListener('alert', e => emit('alert', JSON.parse(e.data)));
    source.onerror = () => {
        if (source.readyState === EventSource.CLOSED) {  // el servidor rechazó la zona (muy grande con el margen)
            if (fallback) return connect(fallback, null);
            return setStatus('idle', t('status.zoom'));
        }
        setStatus('warn', t('status.reconnecting'));
    };
}

/** Conecta o reconecta si la vista salió de la zona pedida; no hace nada en reproducción histórica. */
export function syncViewport() {
    if (state.mode !== 'live' || state.chase) return;
    if (map.getZoom() < state.config.min_zoom) {
        stop();
        return setStatus('idle', t('status.zoom'));
    }
    const view = bounds();
    if (source && contains(connected, view)) return;
    connect(padded(view, PAD), view);
}

/** Mantiene la conexión sobre la zona de un punto (la cámara en primera persona no define una zona útil en el mapa). */
export function followZone(lat, lon) {
    const near = { lamin: lat - 0.1, lamax: lat + 0.1, lomin: lon - 0.1, lomax: lon + 0.1 };
    if (source && contains(connected, near)) return;
    const view = { lamin: lat - 0.6, lamax: lat + 0.6, lomin: lon - 0.6, lomax: lon + 0.6 };
    connect(padded(view, PAD), view);
}

export const syncViewportSoon = debounce(syncViewport, 500);
