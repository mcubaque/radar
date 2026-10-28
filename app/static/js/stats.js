// Panel de estadísticas del historial grabado, con gráficos en HTML/CSS (sin librerías).
import { t } from './i18n.js';
import { onOpen } from './panels.js';
import { state } from './state.js';
import { $, esc, fetchJson } from './util.js';

const hourLabel = ts => new Date(ts * 1000).toLocaleTimeString(state.lang, { hour: '2-digit', minute: '2-digit' });

function hbars(rows, labelOf, valueOf) {
    const max = Math.max(1, ...rows.map(valueOf));
    return `<ul class="hbars">${rows.map(r => `<li><span>${esc(labelOf(r))}</span>
        <div><i style="width:${(valueOf(r) / max) * 100}%"></i></div><b>${valueOf(r).toLocaleString(state.lang)}</b></li>`).join('')}</ul>`;
}

export async function render() {
    const body = $('#stats-body');
    let data;
    try {
        data = await fetchJson(`/api/stats?hours=${$('#stats-hours').value}`);
    } catch (e) {
        body.innerHTML = `<p class="hint">${esc(e.message)}</p>`;
        return;
    }
    if (!data.per_hour.length && !data.altitude.some(a => a.positions)) {
        body.innerHTML = `<p class="hint">${esc(t('stats.empty'))}</p>`;
        return;
    }
    const max = Math.max(1, ...data.per_hour.map(h => h.flights));
    const first = data.per_hour[0], last = data.per_hour[data.per_hour.length - 1];
    const altTotal = data.altitude.reduce((s, a) => s + a.positions, 0) || 1;
    body.innerHTML = `
<h3>${esc(t('stats.perhour'))}</h3>
<div class="vbars" role="img" aria-label="${esc(t('stats.perhour'))}">${data.per_hour.map(h =>
        `<span style="height:${(h.flights / max) * 100}%" title="${esc(hourLabel(h.hour))}: ${h.flights}"></span>`).join('')}</div>
<div class="axis"><small>${first ? esc(hourLabel(first.hour)) : ''}</small><small>max ${max}</small><small>${last ? esc(hourLabel(last.hour)) : ''}</small></div>
${data.airlines.length ? `<h3>${esc(t('stats.airlines'))}</h3>${hbars(data.airlines, a => a.name || a.airline, a => a.flights)}` : ''}
<h3>${esc(t('stats.altitude'))}</h3>${hbars(data.altitude, a => a.band, a => Math.round((a.positions / altTotal) * 100))}
<p class="hint">${esc(t('stats.zone'))}</p>`;
}

export function bindStats() {
    onOpen('stats', render);
    $('#stats-hours').addEventListener('change', render);
}
