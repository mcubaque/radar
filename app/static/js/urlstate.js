// Estado de la vista en la URL (#lat,lon,zoom[,vuelo]) para compartir enlaces, y última vista guardada.
import { map } from './map.js';
import { state } from './state.js';
import { debounce } from './util.js';

const VIEW_KEY = 'skymonitor.view';

const valid = v => Number.isFinite(v.lat) && Number.isFinite(v.lon) && Number.isFinite(v.zoom);

export function readHash() {
    const [lat, lon, zoom, flight] = location.hash.slice(1).split(',');
    const view = { lat: +lat, lon: +lon, zoom: +zoom, flight: /^[0-9a-f]{6}$/i.test(flight || '') ? flight : null };
    return valid(view) && lat !== undefined ? view : null;
}

export function savedView() {
    try {
        const view = JSON.parse(localStorage.getItem(VIEW_KEY));
        return view && valid(view) ? view : null;
    } catch {
        return null;
    }
}

export const writeView = debounce(() => {
    const c = map.getCenter();
    const view = { lat: +c.lat.toFixed(4), lon: +c.lng.toFixed(4), zoom: +map.getZoom().toFixed(1) };
    const parts = [view.lat, view.lon, view.zoom];
    if (state.selected) parts.push(state.selected);
    history.replaceState(null, '', `#${parts.join(',')}`);
    try { localStorage.setItem(VIEW_KEY, JSON.stringify(view)); } catch { /* sin almacenamiento */ }
}, 300);
