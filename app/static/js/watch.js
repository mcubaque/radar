// Lista de seguimiento y alertas.
import { onOpen } from './panels.js';
import { t } from './i18n.js';
import { emit, state } from './state.js';
import { toast } from './toast.js';
import { $, esc, fetchJson } from './util.js';

const TOKEN_KEY = 'skymonitor.admin';

function token() {
    try { return localStorage.getItem(TOKEN_KEY) || ''; } catch { return ''; }
}

/** Petición que añade el token de administrador y lo pide una vez si el servidor lo exige. */
async function request(method, url, body) {
    const send = () => fetchJson(url, {
        method,
        headers: { 'Content-Type': 'application/json', 'X-Admin-Token': token() },
        body: body && JSON.stringify(body),
    });
    try {
        return await send();
    } catch (e) {
        if (e.status !== 401) throw e;
        const entered = prompt(t('watch.token'));
        if (!entered) throw e;
        try { localStorage.setItem(TOKEN_KEY, entered); } catch { /* sin almacenamiento */ }
        return send();
    }
}

export async function addWatch(kind, value, label) {
    await request('POST', '/api/watchlist', { kind, value, label });
    toast(t('watch.added'), { type: 'ok' });
    render();
}

const time = ts => new Date(ts * 1000).toLocaleString(state.lang, { dateStyle: 'short', timeStyle: 'short' });

export async function render() {
    const headers = { 'X-Admin-Token': token() };
    let locked = false;
    const [watch, alerts] = await Promise.all([
        fetchJson('/api/watchlist', { headers }).catch(e => { locked = e.status === 401; return []; }),
        fetchJson('/api/alerts', { headers }).catch(() => []),
    ]);
    $('#watch-list').innerHTML = locked ? `<li class="hint">${esc(t('watch.locked'))}</li>` : watch.length
        ? watch.map(w => `<li class="row"><span><b>${esc(w.value)}</b> <small>${esc(w.kind)}${w.label ? ' · ' + esc(w.label) : ''}</small></span>
            <button class="icon-btn" data-del="${w.id}" aria-label="${esc(t('watch.remove'))}">×</button></li>`).join('')
        : `<li class="hint">${esc(t('watch.empty'))}</li>`;
    $('#alert-list').innerHTML = alerts.length
        ? alerts.map(a => `<li class="row"><span>${esc(a.message)}<br><small>${esc(time(a.ts))}</small></span></li>`).join('')
        : `<li class="hint">${esc(t('watch.noalerts'))}</li>`;
}

export function bindWatch() {
    onOpen('watch', render);
    $('#watch-form').addEventListener('submit', async e => {
        e.preventDefault();
        try {
            await addWatch($('#w-kind').value, $('#w-value').value.trim(), $('#w-label').value.trim());
            e.target.reset();
        } catch (err) {
            toast(err.message, { type: 'error' });
        }
    });
    $('#watch-list').addEventListener('click', async e => {
        const id = e.target.closest('[data-del]')?.dataset.del;
        if (!id) return;
        try { await request('DELETE', `/api/watchlist/${id}`); render(); } catch (err) { toast(err.message, { type: 'error' }); }
    });
    $('#w-notify').addEventListener('click', async () => {
        if (!('Notification' in window) || (await Notification.requestPermission()) !== 'granted') {
            toast(t('watch.denied'), { type: 'error' });
        }
    });
}

/** Alerta recibida por el stream: aviso en pantalla y, si hay permiso, del navegador. */
export function showAlert(alert) {
    toast(`⚠ ${alert.message}`, { type: 'danger', timeout: 15000, onClick: () => emit('pick', alert.icao24, { id: alert.icao24, lat: alert.lat, lon: alert.lon, cs: alert.callsign }) });
    if ('Notification' in window && Notification.permission === 'granted') new Notification('SkyMonitor', { body: alert.message });
}
