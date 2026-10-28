// Tarjeta lateral con el detalle de un vuelo (la de aeropuerto está en airport.js).
import { closeAirportWatch, isAirportOpen } from './airport.js';
import { flights, setTrack } from './flightlayer.js';
import { MAX_AGL_ALT_M, emergencyLabel, heightAboveGround, routeProgress, windComponents } from './flightmodel.js';
import { t } from './i18n.js';
import { emit, state } from './state.js';
import { setRunways } from './weather.js';
import * as units from './units.js';
import { $, esc, fetchJson } from './util.js';

const card = document.getElementById('card');

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
    <span class="badge warn" data-f="int" hidden>${esc(t('card.interesting'))}</span>
  </div>
</header>
<div class="route" data-f="route" hidden>
  <div><b data-f="origin"></b><small data-f="origin-name"></small></div>
  <span class="arrow" aria-hidden="true">✈</span>
  <div><b data-f="destination"></b><small data-f="destination-name"></small></div>
</div>
<div class="progress" data-f="progress" hidden role="img" aria-label="${esc(t('card.progress'))}">
  <div class="bar"><i data-f="bar"></i></div><small data-f="eta"></small>
</div>
<p class="hint" data-f="routenote" hidden>${esc(t('card.routenote'))}</p>
<dl class="grid">
  <div><dt>${esc(t('card.alt'))}</dt><dd data-f="alt">—</dd><small data-f="alt2"></small></div>
  <div><dt>${esc(t('card.agl'))}</dt><dd data-f="agl">—</dd><small data-f="agl2"></small></div>
  <div><dt>${esc(t('card.speed'))}</dt><dd data-f="spd">—</dd><small data-f="spd2"></small></div>
  ${row(t('card.heading'), 'hdg')}${row(t('card.vrate'), 'vr')}${row(t('card.wind'), 'wind')}${row(t('card.tas'), 'tas')}${row(t('card.squawk'), 'sq')}
</dl>
<dl class="info">
  ${row(t('card.reg'), 'reg')}${row(t('card.aircraft'), 'type')}
  ${row(t('card.operator'), 'owner')}${row(t('card.position'), 'pos')}
</dl>
<div class="actions">
  <button class="btn" data-act="follow" aria-pressed="false">${esc(t('card.follow'))}</button>
  <button class="btn" data-act="chase">${esc(t('card.chase'))}</button>
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

// Ruta del vuelo seleccionado (para progreso y ETA) y viento en su altitud
let currentRoute = null;
let windInfo = { at: 0, wind: null };

async function ensureWind(rec) {
    if (rec.gnd || rec.alt == null || Date.now() - windInfo.at < 60000) return;
    windInfo = { ...windInfo, at: Date.now() };  // tambien tras un fallo, para no insistir cada segundo
    try {
        const { wind } = await fetchJson(`/api/wind?lat=${rec.lat}&lon=${rec.lon}&alt=${Math.round(rec.alt)}`);
        windInfo = { at: Date.now(), wind };
        refreshLive();
    } catch { /* sin dato: viento y velocidad aerodinámica quedan en "—" */ }
}

function fillWind(rec) {
    const { wind } = windInfo;
    if (rec.gnd || !wind || rec.spd == null || rec.hdg == null) {
        setText('wind', '—');
        setText('tas', '—');
        return;
    }
    const { headKt, crossKt, tasKt } = windComponents(rec.hdg, rec.spd, wind.dir, wind.kt);
    const main = Math.abs(headKt) >= Math.abs(crossKt) ? [headKt, headKt >= 0 ? 'card.headwind' : 'card.tailwind'] : [crossKt, 'card.crosswind'];
    const toUnit = kt => units.speed(Math.abs(kt) / 1.94384)[0];
    setText('wind', `${toUnit(main[0])} ${t(main[1])}`);
    setText('tas', `≈ ${units.speed(tasKt / 1.94384)[0]}`);
}

function fillProgress(rec) {
    const el = field('progress');
    if (!el) return;
    const o = currentRoute?.origin, d = currentRoute?.destination;
    const p = o?.lat != null && d?.lat != null && !rec.gnd ? routeProgress(o, d, rec.lat, rec.lon, rec.spd) : null;
    el.hidden = !p;
    if (!p) return;
    field('bar').style.width = `${Math.round(p.fraction * 100)}%`;
    const left = `${units.distance(p.remainingKm)} ${t('card.remaining')}`;
    const eta = p.etaMin == null ? '' : ` · ${t('card.eta')} ${p.etaMin >= 60 ? `${Math.floor(p.etaMin / 60)} h ${p.etaMin % 60} min` : `${p.etaMin} min`}`;
    setText('eta', left + eta);
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
    ensureWind(rec);
    fillWind(rec);
    fillProgress(rec);
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
    field('int').hidden = !rec.int || !!rec.mil;
    const em = field('em');
    em.hidden = !rec.em;
    em.textContent = rec.em ? `${t('card.emergency')} ${rec.sq || ''}`.trim() : '';
    em.title = rec.em ? emergencyLabel(rec) : '';
    $('[data-act="follow"]', card)?.setAttribute('aria-pressed', String(state.follow));
}

export function refreshLive() {
    if (!state.selected || isAirportOpen()) return;
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
    currentRoute = route;
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
    currentRoute = null;
    windInfo = { at: 0, wind: null };
    setRunways();
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
    setRunways();
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
