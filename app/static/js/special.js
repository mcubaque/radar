// Aeronaves especiales a la vista: emergencias, militares, de interés y tipos poco comunes.
import { visibleFlights } from './flightlayer.js';
import { specialReason } from './flightmodel.js';
import { t } from './i18n.js';
import { map } from './map.js';
import { onOpen } from './panels.js';
import { emit, on, savePrefs, state } from './state.js';
import { toast } from './toast.js';
import { $, esc } from './util.js';

const seen = new Set();  // ya avisadas en esta sesión
let primed = false;      // la primera carga no avisa: son las que ya estaban en el aire

function inView() {
    const bounds = map.getBounds();
    return visibleFlights().filter(f => bounds.contains([f.lon, f.lat]))
        .map(f => ({ f, reason: specialReason(f) })).filter(x => x.reason);
}

export function render() {
    const list = inView();
    $('#special-list').innerHTML = list.length
        ? list.map(({ f, reason }) => `<li><button class="row-btn" data-pick="${esc(f.id)}">
            <b>${esc(f.cs || f.id)}</b><span>${esc(f.ty || '')}</span><span class="tag ${reason}">${esc(t(`special.${reason}`))}</span></button></li>`).join('')
        : `<li class="hint">${esc(t('special.empty'))}</li>`;
    const badge = $('#special-badge');
    badge.hidden = list.length === 0;
    badge.textContent = list.length;
}

function announce() {
    // las emergencias ya tienen su propio aviso
    const fresh = inView().filter(({ f, reason }) => reason !== 'emergency' && !seen.has(f.id));
    for (const { f } of fresh) seen.add(f.id);
    if (!primed) {
        primed = visibleFlights().length > 0;  // lo que ya estaba en el aire al abrir no cuenta como novedad
        return;
    }
    if (!state.notifySpecial) return;
    for (const { f, reason } of fresh.slice(0, 3)) {
        toast(`★ ${t('special.appeared')}: ${f.cs || f.id} ${f.ty || ''} · ${t(`special.${reason}`)}`, {
            type: 'ok', timeout: 8000, onClick: () => emit('pick', f.id),
        });
    }
}

export function bindSpecial() {
    $('#special-notify').checked = state.notifySpecial;
    $('#special-notify').addEventListener('change', e => { state.notifySpecial = e.target.checked; savePrefs(); });
    $('#special-list').addEventListener('click', e => {
        const id = e.target.closest('[data-pick]')?.dataset.pick;
        if (id) emit('pick', id);
    });
    onOpen('special', render);
    on('flights', () => { announce(); render(); });
    map.on('moveend', render);
}
