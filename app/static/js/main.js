import { openAirport } from './airport.js';
import { bindChase, startChase, stopChase } from './chase.js';
import { closeCard, openFlight, refreshLive, setFollowButton } from './card.js';
import { bindExtras, refreshAirportsSoon } from './extras.js';
import { bindPicking, flights, redraw, startAnimation, visibleFlights } from './flightlayer.js';
import { applyI18n, t } from './i18n.js';
import { initMap, map } from './map.js';
import {
    anyOpen, applyTheme, bindFilters, bindLayers, bindList, bindSettings, bindToolbar, closePanel, renderList,
} from './panels.js';
import { bindReplay, exitReplay, loadFrameSoon } from './replay.js';
import { bindSearch } from './search.js';
import { on, state } from './state.js';
import { bindSpecial } from './special.js';
import { bindStats } from './stats.js';
import { onStatus, syncViewport, syncViewportSoon } from './stream.js';
import { toast } from './toast.js';
import { $, $$, debounce, fetchJson, isCompact } from './util.js';
import { readHash, savedView, writeView } from './urlstate.js';
import { bindWeather } from './weather.js';
import { addWatch, bindWatch, render as renderWatch, showAlert } from './watch.js';

const DEFAULT_VIEW = { lat: 40.7, lon: -74, zoom: 8 };

// --- estado de conexión ---

const statusEl = $('#status');
let lastStatus = { kind: 'idle', text: t('status.connecting') };

function showStatus(kind, text) {
    lastStatus = { kind, text };
    statusEl.dataset.kind = kind;
    $('.txt', statusEl).textContent = text;
}

const compactNumber = n => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));

/** Fuente activa y créditos de OpenSky; `slow` indica que el servidor espacia las peticiones para cuidar la cuota. */
function sourceText() {
    const m = state.meta;
    if (!m?.source) return '';
    const credits = m.credits != null ? ` · ${compactNumber(m.credits)} ${t('status.credits')}` : '';
    return ` · ${m.source}${credits}`;
}

function showCount() {
    if (state.mode === 'replay') return;
    const text = `${t('status.flights', { n: visibleFlights().length })} · ${t('status.live')}${sourceText()}`;
    showStatus(state.meta?.slow > 1 ? 'warn' : 'ok', text);
    const m = state.meta;
    statusEl.title = m?.source
        ? `${t('status.src')}: ${m.source}${m.credits != null ? ` · ${m.credits} ${t('status.credits')}` : ''}${m.slow > 1 ? ` · ${t('status.slow')}` : ''}`
        : '';
}

// --- emergencias ---

const emergencyEl = $('#emergency');

function renderEmergency() {
    const list = [...flights.values()].filter(f => f.em);
    emergencyEl.hidden = list.length === 0;
    if (!list.length) return;
    const f = list[0];
    emergencyEl.dataset.id = f.id;
    emergencyEl.textContent = `⚠ ${t('card.emergency')} ${f.sq || ''} · ${f.cs || f.id}${list.length > 1 ? ` (+${list.length - 1})` : ''}`;
}

// --- selección ---

function pick(id, fallback) {
    if (isCompact()) closePanel();  // en pantallas compactas la tarjeta ocupa el mismo espacio
    const rec = flights.get(id) || fallback;
    if (rec && !map.getBounds().contains([rec.lon, rec.lat])) map.flyTo({ center: [rec.lon, rec.lat], zoom: Math.max(map.getZoom(), 8) });
    openFlight(id, rec);
}

function pickAirport(a) {
    openAirport(a.iata || a.icao || a.ident, a.lat, a.lon);
}

const toggleFollow = () => {
    if (!state.selected) return;
    state.follow = !state.follow;
    setFollowButton();
};

async function cardAction(action) {
    const rec = flights.get(state.selected);
    if (action === 'close') closeCard();
    else if (action === 'follow') toggleFollow();
    else if (action === 'chase') startChase(state.selected);
    else if (action === 'share') {
        await navigator.clipboard?.writeText(location.href).catch(() => {});
        toast(t('common.copied'), { type: 'ok', timeout: 2500 });
    } else if (action === 'watch' && rec) {
        const [kind, value] = rec.cs ? ['callsign', rec.cs] : rec.reg ? ['registration', rec.reg] : ['icao24', rec.id];
        addWatch(kind, value, null).catch(e => toast(e.message, { type: 'error' }));
    }
}

// --- arranque ---

function locateOnce() {
    navigator.geolocation?.getCurrentPosition(
        p => map.flyTo({ center: [p.coords.longitude, p.coords.latitude], zoom: 8 }),
        () => toast(t('common.error'), { type: 'error', timeout: 3000 }),
    );
}

async function boot() {
    applyI18n();
    applyTheme();
    state.config = await fetchJson('/api/config').catch(() => state.config);
    $$('[data-history]').forEach(el => (el.hidden = !state.config.history));
    $('#btn-replay').hidden = !state.config.history;

    const hash = readHash();
    const saved = savedView();
    initMap(hash ?? saved ?? DEFAULT_VIEW);
    bindPicking();
    startAnimation();

    bindToolbar(); bindList(); bindFilters(); bindLayers(); bindSettings();
    bindSearch(); bindStats(); bindWatch(); bindReplay(); bindExtras(); bindWeather(); bindChase(); bindSpecial();

    onStatus((kind, text) => (text ? showStatus(kind, text) : showCount()));
    on('meta', m => { state.meta = m; showCount(); });
    on('pick', pick);
    on('pick-airport', pickAirport);
    on('card-action', cardAction);
    on('alert', alert => { showAlert(alert); renderWatch(); });
    on('select', () => {
        writeView();
        // en móvil la tarjeta es una hoja inferior: se desplaza el centro del mapa para no tapar el avión
        map.setPadding({ top: 0, left: 0, right: 0, bottom: isCompact() && state.selected ? Math.round(innerHeight * 0.45) : 0 });
    });
    on('units', () => { redraw(); refreshLive(); renderList(); });
    on('lang', () => { showStatus(lastStatus.kind, lastStatus.text); showCount(); });
    on('replay-time', count => {
        const empty = count === 0 ? ` · ${t('replay.nodata')}` : '';
        showStatus('idle', `${t('status.replay')} · ${$('#rp-time').textContent}${empty}`);
    });

    const refreshList = debounce(renderList, 400);
    on('flights', () => {
        showCount();
        renderEmergency();
        refreshLive();
        refreshList();
    });

    map.on('moveend', () => {
        writeView();
        refreshAirportsSoon();
        if (state.mode === 'replay') loadFrameSoon(); else syncViewportSoon();
        refreshList();
    });
    map.on('dragstart', () => { if (state.follow) { state.follow = false; setFollowButton(); } });
    map.on('click', e => {
        if (!map.queryRenderedFeatures(e.point, { layers: ['planes'] }).length) closeCard();
    });
    map.once('load', () => {
        syncViewport();
        if (hash?.flight) pick(hash.flight);
        else if (!hash && !saved && 'geolocation' in navigator) locateOnce();
    });

    emergencyEl.addEventListener('click', () => pick(emergencyEl.dataset.id));
    $('#btn-locate').addEventListener('click', locateOnce);

    document.addEventListener('keydown', e => {
        const typing = ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName);
        if (e.key === 'Escape') {
            if (state.chase) stopChase();
            else if (anyOpen()) closePanel();
            else if (state.mode === 'replay') exitReplay();
            else closeCard();
        } else if (e.key.toLowerCase() === 'f' && !typing && !e.ctrlKey && !e.metaKey) toggleFollow();
    });

    window.addEventListener('offline', () => showStatus('error', t('offline')));
    window.addEventListener('online', syncViewport);
    if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
}

boot();
