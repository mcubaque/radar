// Cajón lateral y sus paneles sencillos: lista de vuelos, filtros, capas y ajustes.
import { ALT_COLORS, ALT_STEPS, GROUND_COLOR, activeFilterCount } from './flightmodel.js';
import { visibleFlights } from './flightlayer.js';
import { applyI18n, t } from './i18n.js';
import { map, setBasemap } from './map.js';
import { emit, on, resolvedTheme, savePrefs, state } from './state.js';
import * as units from './units.js';
import { $, $$, esc } from './util.js';

const drawer = document.getElementById('drawer');
const hooks = {}; // panel -> función que se ejecuta al abrirlo
export const onOpen = (panel, fn) => (hooks[panel] = fn);
let current = null;

export function openPanel(name) {
    current = name;
    drawer.hidden = false;
    $('#drawer-title').textContent = t(`${name}.title`);
    for (const section of $$('section[data-panel]', drawer)) section.hidden = section.dataset.panel !== name;
    for (const btn of $$('#toolbar [data-panel]')) btn.classList.toggle('active', btn.dataset.panel === name);
    hooks[name]?.();
}

export function closePanel() {
    current = null;
    drawer.hidden = true;
    for (const btn of $$('#toolbar [data-panel]')) btn.classList.remove('active');
}

export const anyOpen = () => current !== null;

export function bindToolbar() {
    for (const btn of $$('#toolbar [data-panel]')) {
        btn.addEventListener('click', () => (current === btn.dataset.panel ? closePanel() : openPanel(btn.dataset.panel)));
    }
    $('#drawer-close').addEventListener('click', closePanel);
}

// --- lista de vuelos visibles ---

const sortKeys = {
    alt: (a, b) => (b.alt ?? -1) - (a.alt ?? -1),
    spd: (a, b) => (b.spd ?? -1) - (a.spd ?? -1),
    cs: (a, b) => (a.cs || a.id).localeCompare(b.cs || b.id),
};

export function renderList() {
    if (current !== 'list') return;
    const bounds = map.getBounds();
    const rows = visibleFlights()
        .filter(f => bounds.contains([f.lon, f.lat]))
        .sort(sortKeys[$('#list-sort').value])
        .slice(0, 150);
    $('#flight-list').innerHTML = rows.length
        ? rows.map(f => `<li><button class="row-btn" data-pick="${esc(f.id)}">
            <b>${esc(f.cs || f.id)}</b><span>${esc(f.ty || '')}</span>
            <span>${esc(f.gnd ? t('card.ground') : units.altitude(f.alt)[0])} · ${esc(units.speed(f.spd)[0])}</span></button></li>`).join('')
        : `<li class="hint">${esc(t('list.empty'))}</li>`;
}

export function bindList() {
    $('#list-sort').addEventListener('change', renderList);
    $('#flight-list').addEventListener('click', e => {
        const id = e.target.closest('[data-pick]')?.dataset.pick;
        if (id) emit('pick', id);
    });
    onOpen('list', renderList);
}

// --- filtros ---

function reflectFilters() {
    const f = state.filters;
    $('#f-ground').checked = f.hideGround;
    $('#f-mil').checked = f.military;
    $('#f-type').value = f.type;
    $('#f-alt').value = f.altBand;
    $('#f-text').value = f.text;
    const count = activeFilterCount(f);
    const badge = $('#filter-badge');
    badge.hidden = count === 0;
    badge.textContent = count;
}

export function bindFilters() {
    const update = () => {
        Object.assign(state.filters, {
            hideGround: $('#f-ground').checked, military: $('#f-mil').checked,
            type: $('#f-type').value, altBand: $('#f-alt').value, text: $('#f-text').value,
        });
        savePrefs();
        reflectFilters();
        emit('filters');
        renderList();
    };
    for (const id of ['f-ground', 'f-mil', 'f-type', 'f-alt']) $(`#${id}`).addEventListener('change', update);
    $('#f-text').addEventListener('input', update);
    $('#f-reset').addEventListener('click', () => {
        Object.assign(state.filters, { hideGround: false, military: false, type: 'all', altBand: 'all', text: '' });
        savePrefs();
        reflectFilters();
        emit('filters');
        renderList();
    });
    reflectFilters();
}

// --- capas y leyenda ---

function renderLegend() {
    const bounds = [0, ...ALT_STEPS];
    const items = [`<li><i style="background:${GROUND_COLOR}"></i>${esc(t('layers.ground'))}</li>`];
    ALT_COLORS.forEach((color, i) => {
        const [from] = units.altitude(bounds[i]);
        const label = i === ALT_COLORS.length - 1 ? `> ${from}` : `${from} – ${units.altitude(bounds[i + 1])[0]}`;
        items.push(`<li><i style="background:${color}"></i>${esc(label)}</li>`);
    });
    $('#legend').innerHTML = items.join('');
}

export function bindLayers() {
    for (const name of ['trails', 'airports', 'rain', 'sigmet']) {
        const box = $(`#l-${name}`);
        box.checked = state.layers[name];
        box.addEventListener('change', () => {
            state.layers[name] = box.checked;
            savePrefs();
            emit('layers', name);
        });
    }
    renderLegend();
    onOpen('layers', renderLegend);
    on('units', renderLegend);
}

// --- ajustes ---

export function applyTheme() {
    const theme = resolvedTheme();
    const changed = document.documentElement.dataset.theme !== theme;
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]').content = theme === 'dark' ? '#0b1220' : '#ffffff';
    if (changed && map) setBasemap(theme);
}

export function bindSettings() {
    $('#s-theme').value = state.theme;
    $('#s-units').value = state.units;
    $('#s-lang').value = state.lang;
    $('#s-theme').addEventListener('change', e => { state.theme = e.target.value; savePrefs(); applyTheme(); });
    $('#s-units').addEventListener('change', e => { state.units = e.target.value; savePrefs(); emit('units'); });
    $('#s-lang').addEventListener('change', e => {
        state.lang = e.target.value;
        savePrefs();
        applyI18n();
        if (current) $('#drawer-title').textContent = t(`${current}.title`);
        emit('lang');
    });
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => state.theme === 'auto' && applyTheme());

    let installEvent = null;
    window.addEventListener('beforeinstallprompt', e => {
        e.preventDefault();
        installEvent = e;
        $('#s-install').hidden = false;
    });
    $('#s-install').addEventListener('click', async () => {
        installEvent?.prompt();
        installEvent = null;
        $('#s-install').hidden = true;
    });
}
