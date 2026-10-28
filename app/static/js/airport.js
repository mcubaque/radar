// Tarjeta lateral de un aeropuerto: clima, METAR/TAF, pistas, llegadas y salidas, refrescada cada 15 s.
import { setTrack } from './flightlayer.js';
import { t } from './i18n.js';
import { map } from './map.js';
import { emit, state } from './state.js';
import { toast } from './toast.js';
import * as units from './units.js';
import { esc, fetchJson } from './util.js';
import { setRunways } from './weather.js';

const card = document.getElementById('card');
let airportWatcher = null;

export function closeAirportWatch() {
    if (airportWatcher) clearInterval(airportWatcher);
    airportWatcher = null;
}

export const isAirportOpen = () => airportWatcher !== null;

const flightRow = f => `<li><button class="row-btn" data-pick="${esc(f.id)}"><b>${esc(f.cs || f.id)}</b>
    <span>${esc(units.distance(f.dist_km))} · ${esc(units.altitude(f.alt)[0])}</span></button></li>`;

function weatherText(w) {
    if (!w) return '—';
    const wind = `${Math.round(w.wind_direction_10m)}° ${Math.round(w.wind_speed_10m)} kt`;
    return `${Math.round(w.temperature_2m)} °C · ${t('airport.wind')} ${wind}`;
}

const CATEGORY_CLASS = { VFR: 'ok', MVFR: 'info', IFR: 'warn', LIFR: 'danger' };

function metarBlock(m, taf) {
    if (!m) return `<p class="hint">${esc(t('airport.nometar'))}</p>`;
    const clouds = (m.clouds || []).map(c => `${c.cover} ${units.altitude(c.base * 0.3048)[0]}`).join(', ');
    const gust = m.wgst ? `G${m.wgst}` : '';
    return `<div class="metar">
  <span class="badge cat ${CATEGORY_CLASS[m.fltCat] || ''}">${esc(m.fltCat || '—')}</span>
  <code>${esc(m.rawOb)}</code>
  <dl class="info">
    <div><dt>${esc(t('airport.wind'))}</dt><dd>${esc(m.wdir ?? '—')}° ${esc(m.wspd ?? '—')}${esc(gust)} kt</dd></div>
    <div><dt>${esc(t('airport.vis'))}</dt><dd>${esc(m.visib != null ? `${m.visib} SM` : '—')}</dd></div>
    <div><dt>${esc(t('airport.clouds'))}</dt><dd>${esc(clouds || '—')}</dd></div>
    <div><dt>${esc(t('airport.qnh'))}</dt><dd>${esc(m.altim ?? '—')} hPa</dd></div>
  </dl>
  ${taf?.raw ? `<details><summary>${esc(t('airport.taf'))}</summary><code>${esc(taf.raw)}</code></details>` : ''}
</div>`;
}

function runwaysBlock(data) {
    if (!data.runways.length) return '';
    const items = data.runways.map(r => `${r.le_ident}/${r.he_ident} · ${units.altitude(r.length_ft * 0.3048)[0]}`).join('  ·  ');
    return `<dl class="info">
  <div><dt>${esc(t('airport.runway'))}</dt><dd>${esc(data.runway_in_use || '—')}</dd></div>
  <div><dt>${esc(t('airport.runways'))}</dt><dd>${esc(items)}</dd></div>
</dl>`;
}

function frequenciesBlock(list) {
    if (!list?.length) return '';
    const items = list.map(f => `<li><span>${esc(f.type)}</span><span>${esc(f.description)}</span><b>${f.mhz.toFixed(3)}</b></li>`).join('');
    return `<h3>${esc(t('airport.freq'))}</h3><ul class="freqs">${items}</ul><p class="hint">${esc(t('airport.freq.hint'))}</p>`;
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
<h3>${esc(t('airport.metar'))}</h3>${metarBlock(data.metar, data.taf)}
${runwaysBlock(data)}
${frequenciesBlock(data.frequencies)}
<a class="btn" target="_blank" rel="noopener noreferrer" href="https://www.liveatc.net/search/?icao=${encodeURIComponent(a.icao)}">🎧 ${esc(t('airport.atc'))}</a>
<p class="hint">${esc(t('airport.atc.hint'))}</p>
<h3>${esc(t('airport.arriving'))}</h3>${list(data.arriving)}
<h3>${esc(t('airport.departing'))}</h3>${list(data.departing)}`;
    setRunways(data.runways, data.runway_in_use);
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
