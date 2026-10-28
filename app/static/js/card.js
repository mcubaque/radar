// Tarjeta lateral: detalle de un vuelo o de un aeropuerto.
import { flights, setTrack } from './flightlayer.js';
import { MAX_AGL_ALT_M, emergencyLabel, heightAboveGround } from './flightmodel.js';
import { t } from './i18n.js';
import { map } from './map.js';
import { emit, state } from './state.js';
import { toast } from './toast.js';
import * as units from './units.js';
import { $, esc, fetchJson } from './util.js';

const card = document.getElementById('card');
let airportWatcher = null;

const field = name => $(`[data-f="${name}"]`, card);
const setText = (name, text) => { const el = field(name); if (el) el.textContent = text ?? ''; };
const row = (label, name) => `<div><dt>${esc(label)}</dt><dd data-f="${name}">—</dd></div>`;

function flightTemplate() {
    return `
<button class="icon-btn close" data-act="close" aria-label="${esc(t('card.close'))}">×</button>
<figure class="photo" data-f="photo" hidden><img alt=""><figcaption><a target="_blank" rel="noopener"></a></figcaption></figure>
<header>
  <h2 data-f="callsign"></h2>
  <div class="sub" data-f="sub"></div>
  <div class="badges">
    <span class="badge" data-f="status"></span>
    <span class="badge warn" data-f="mil" hidden>${esc(t('card.military'))}</span>
    <span class="badge danger" data-f="em" hidden></span>
  </div>
</header>
<div class="route" data-f="route" hidden>
  <div><b data-f="origin"></b><small data-f="origin-name"></small></div>
  <span class="arrow" aria-hidden="true">✈</span>
  <div><b data-f="destination"></b><small data-f="destination-name"></small></div>
</div>
<p class="hint" data-f="routenote" hidden>${esc(t('card.routenote'))}</p>
<dl class="grid">
  <div><dt>${esc(t('card.alt'))}</dt><dd data-f="alt">—</dd><small data-f="alt2"></small></div>
  <div><dt>${esc(t('card.agl'))}</dt><dd data-f="agl">—</dd><small data-f="agl2"></small></div>
  <div><dt>${esc(t('card.speed'))}</dt><dd data-f="spd">—</dd><small data-f="spd2"></small></div>
  ${row(t('card.heading'), 'hdg')}${row(t('card.vrate'), 'vr')}${row(t('card.squawk'), 'sq')}
</dl>
<dl class="info">
  ${row(t('card.reg'), 'reg')}${row(t('card.aircraft'), 'type')}
  ${row(t('card.operator'), 'owner')}${row(t('card.position'), 'pos')}
</dl>
<div class="actions">
  <button class="btn" data-act="follow" aria-pressed="false">${esc(t('card.follow'))}</button>
  <button class="btn" data-act="watch">${esc(t('card.watch'))}</button>
  <button class="btn" data-act="share">${esc(t('card.share'))}</button>
</div>`;
}

// Presion en superficie bajo el avion seleccionado, para calcular su altura sobre el terreno
let reference = { key: null, hpa: null };
let referencePending = false;

async function ensureReference(rec) {
    const key = `${rec.lat.toFixed(1)},${rec.lon.toFixed(1)}`;  // la presion varia poco: una consulta por ~11 km
    if (key === reference.key || referencePending) return;
    referencePending = true;
    try {
        const { surface_hpa: hpa } = await fetchJson(`/api/reference?lat=${rec.lat}&lon=${rec.lon}`);
        reference = { key, hpa };
        refreshLive();
    } catch { /* sin dato: la altura sobre el terreno queda en "—" */ } finally {
        referencePending = false;
    }
}

function fillAltitudes(rec) {
    const [alt, alt2] = units.altitude(rec.alt);
    setText('alt', rec.gnd ? '—' : alt);
    setText('alt2', rec.gnd ? '' : alt2);
    let agl = null;  // m sobre el terreno; 0 en tierra
    if (rec.gnd) agl = 0;
    else if (rec.alt != null && rec.alt < MAX_AGL_ALT_M && reference.hpa) agl = heightAboveGround(rec.alt, reference.hpa);
    const [aglMain, aglOther] = agl == null ? ['—', ''] : units.altitude(agl);
    setText('agl', agl == null || rec.gnd ? aglMain : `≈ ${aglMain}`);
    setText('agl2', agl == null || rec.gnd ? '' : aglOther);
}

export function fillLive(rec) {
    setText('callsign', rec.cs || rec.id.toUpperCase());
    const [spd, spd2] = units.speed(rec.spd);
    fillAltitudes(rec);
    ensureReference(rec);
    setText('spd', spd);
    setText('spd2', spd2);
    setText('hdg', units.heading(rec.hdg));
    setText('vr', units.verticalRate(rec.vr));
    setText('sq', rec.sq || '—');
    setText('pos', `${rec.lat.toFixed(3)}, ${rec.lon.toFixed(3)}`);
    const live = flights.has(rec.id) || Date.now() / 1000 - rec.ts < 90;  // reciente aunque aun no llegue al mapa
    setText('status', live ? (rec.gnd ? t('card.ground') : t('card.airborne')) : t('card.nosignal'));
    field('status')?.classList.toggle('ground', !live || !!rec.gnd);
    field('mil').hidden = !rec.mil;
    const em = field('em');
    em.hidden = !rec.em;
    em.textContent = rec.em ? `${t('card.emergency')} ${rec.sq || ''}`.trim() : '';
    em.title = rec.em ? emergencyLabel(rec) : '';
    $('[data-act="follow"]', card)?.setAttribute('aria-pressed', String(state.follow));
}

export function refreshLive() {
    if (!state.selected || airportWatcher !== null) return;
    const rec = flights.get(state.selected);
    if (rec) {
        card.dataset.last = JSON.stringify(rec);
        fillLive(rec);
    } else if (card.dataset.last) {
        fillLive(JSON.parse(card.dataset.last));
    }
}

function airportText(a) { return a ? a.iata || a.icao || '—' : '—'; }
function airportName(a) { return a ? [a.name, a.country].filter(Boolean).join(' · ') : ''; }

function fillDetails(data) {
    const { aircraft, airline, route } = data;
    setText('sub', [airline?.name, aircraft.description || aircraft.type_code].filter(Boolean).join(' · '));
    setText('reg', aircraft.registration || '—');
    setText('type', aircraft.description || aircraft.type_code || '—');
    setText('owner', airline?.name || aircraft.owner || '—');
    if (data.military) field('mil').hidden = false;
    field('route').hidden = field('routenote').hidden = !route;
    if (route) {
        setText('origin', airportText(route.origin));
        setText('origin-name', airportName(route.origin));
        setText('destination', airportText(route.destination));
        setText('destination-name', airportName(route.destination));
    }
}

function fillPhoto({ photo }) {
    const figure = field('photo');
    figure.hidden = !photo;
    if (!photo) return;
    $('img', figure).src = photo.url;
    const credit = $('a', figure);
    credit.href = photo.link;
    credit.textContent = `© ${photo.photographer || 'Planespotters'}`;
}

function trackPoints(id, points) {
    if (points.length > 1) return points;
    const rec = flights.get(id);  // sin historial grabado: usa la estela de esta sesión
    return rec ? rec.trail.map(([lon, lat]) => [lat, lon]) : [];
}

export async function openFlight(id, fallback) {
    closeAirportWatch();
    state.selected = id;
    state.follow = false;
    reference = { key: null, hpa: null };
    emit('select');
    card.innerHTML = flightTemplate();
    card.hidden = false;
    delete card.dataset.last;
    const rec = flights.get(id) || fallback;
    if (rec) {
        card.dataset.last = JSON.stringify(rec);
        fillLive(rec);
    }
    const callsign = encodeURIComponent(rec?.cs || '');
    const until = state.mode === 'replay' && state.replayTime ? `?until=${state.replayTime}` : '';
    const stillHere = () => state.selected === id;

    fetchJson(`/api/aircraft/${id}?callsign=${callsign}`).then(d => stillHere() && fillDetails(d)).catch(() => {});
    fetchJson(`/api/photo/${id}`).then(d => stillHere() && fillPhoto(d)).catch(() => {});
    fetchJson(`/api/track/${id}${until}`)
        .catch(() => [])
        .then(points => stillHere() && setTrack(trackPoints(id, points)));
}

export function closeCard() {
    closeAirportWatch();
    card.hidden = true;
    if (state.selected) {
        state.selected = null;
        state.follow = false;
        emit('select');
    }
    setTrack([]);
}

// --- aeropuerto ---

function closeAirportWatch() {
    if (airportWatcher) clearInterval(airportWatcher);
    airportWatcher = null;
}

const flightRow = f => `<li><button class="row-btn" data-pick="${esc(f.id)}"><b>${esc(f.cs || f.id)}</b>
    <span>${esc(units.distance(f.dist_km))} · ${esc(units.altitude(f.alt)[0])}</span></button></li>`;

function weatherText(w) {
    if (!w) return '—';
    const wind = `${Math.round(w.wind_direction_10m)}° ${Math.round(w.wind_speed_10m)} kt`;
    return `${Math.round(w.temperature_2m)} °C · ${t('airport.wind')} ${wind}`;
}

async function renderAirport(code) {
    const data = await fetchJson(`/api/airport/${encodeURIComponent(code)}`);
    const a = data.airport;
    const list = items => (items.length ? `<ul class="rows">${items.map(flightRow).join('')}</ul>` : `<p class="hint">${esc(t('airport.none'))}</p>`);
    card.innerHTML = `
<button class="icon-btn close" data-act="close" aria-label="${esc(t('card.close'))}">×</button>
<header><h2>${esc(a.iata || a.icao)} <small>${esc(a.icao)}</small></h2><div class="sub">${esc(a.name)}</div>
  <div class="sub">${esc([a.city, a.country].filter(Boolean).join(', '))}</div></header>
<dl class="info">
  <div><dt>${esc(t('airport.weather'))}</dt><dd>${esc(weatherText(data.weather))}</dd></div>
  <div><dt>${esc(t('airport.elevation'))}</dt><dd>${esc(units.altitude((a.elevation_ft ?? 0) * 0.3048)[0])}</dd></div>
  <div><dt>${esc(t('airport.ground'))}</dt><dd>${data.ground}</dd></div>
  <div><dt>${esc(t('airport.near'))}</dt><dd>${data.airborne_near}</dd></div>
</dl>
<h3>${esc(t('airport.arriving'))}</h3>${list(data.arriving)}
<h3>${esc(t('airport.departing'))}</h3>${list(data.departing)}`;
}

export async function openAirport(code, lat, lon) {
    closeAirportWatch();
    if (state.selected) { state.selected = null; emit('select'); }
    setTrack([]);
    card.hidden = false;
    if (lat != null) map.flyTo({ center: [lon, lat], zoom: Math.max(map.getZoom(), 9) });
    const load = () => renderAirport(code).catch(() => toast(t('common.error'), { type: 'error' }));
    await load();
    airportWatcher = setInterval(load, 15000);
}

// --- acciones de la tarjeta ---

card.addEventListener('click', e => {
    const pick = e.target.closest('[data-pick]');
    if (pick) return emit('pick', pick.dataset.pick);
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (act) emit('card-action', act);
});

export function setFollowButton() {
    $('[data-act="follow"]', card)?.setAttribute('aria-pressed', String(state.follow));
}
