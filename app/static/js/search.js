// Búsqueda con sugerencias de vuelos y aeropuertos, navegable con teclado.
import { t } from './i18n.js';
import { map } from './map.js';
import { emit } from './state.js';
import { debounce, esc, fetchJson } from './util.js';

const input = document.getElementById('search');
const list = document.getElementById('suggestions');
let items = [];
let active = -1;

function close() {
    list.hidden = true;
    input.setAttribute('aria-expanded', 'false');
    active = -1;
}

function highlight(index) {
    active = index;
    [...list.querySelectorAll('[role="option"]')].forEach((el, i) => {
        el.setAttribute('aria-selected', String(i === index));
        if (i === index) el.scrollIntoView({ block: 'nearest' });
    });
}

function choose(item) {
    close();
    input.value = '';
    input.blur();
    if (item.kind === 'airport') {
        emit('pick-airport', item.data);
    } else {
        map.flyTo({ center: [item.data.lon, item.data.lat], zoom: Math.max(map.getZoom(), 9) });
        emit('pick', item.data.id, item.data);
    }
}

function render(result) {
    items = [
        ...result.flights.map(data => ({ kind: 'flight', data })),
        ...result.airports.map(data => ({ kind: 'airport', data })),
    ];
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
    if (!items.length) {
        list.innerHTML = `<li class="empty">${esc(t('search.none'))}</li>`;
        return;
    }
    list.innerHTML = items.map(({ kind, data }, i) => kind === 'flight'
        ? `<li role="option" data-i="${i}"><b>${esc(data.cs || data.id)}</b><span>${esc([data.reg, data.ty].filter(Boolean).join(' · '))}</span></li>`
        : `<li role="option" data-i="${i}"><b>${esc(data.iata || data.icao)}</b><span>${esc(data.name)} · ${esc(data.city || '')}</span></li>`).join('');
    highlight(-1);
}

const search = debounce(async () => {
    const q = input.value.trim();
    if (q.length < 2) return close();
    try {
        render(await fetchJson(`/api/search?q=${encodeURIComponent(q)}`));
    } catch {
        close();
    }
}, 250);

export function bindSearch() {
    input.addEventListener('input', search);
    input.addEventListener('keydown', e => {
        if (e.key === 'ArrowDown') { e.preventDefault(); highlight(Math.min(items.length - 1, active + 1)); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); highlight(Math.max(0, active - 1)); }
        else if (e.key === 'Enter' && items.length) choose(items[Math.max(0, active)]);
        else if (e.key === 'Escape') { close(); input.blur(); }
    });
    list.addEventListener('mousedown', e => {  // mousedown: ocurre antes de que el input pierda el foco
        const li = e.target.closest('[data-i]');
        if (li) choose(items[+li.dataset.i]);
    });
    input.addEventListener('blur', () => setTimeout(close, 100));
    document.addEventListener('keydown', e => {
        if (e.key === '/' && !['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
            e.preventDefault();
            input.focus();
        }
    });
}
