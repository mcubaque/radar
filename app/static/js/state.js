// Estado compartido de la interfaz, preferencias persistentes y un bus de eventos mínimo.

const KEY = 'skymonitor.prefs';

const defaults = {
    units: 'aviation', // aviation = ft/kt, metric = m/km/h
    lang: (typeof navigator !== 'undefined' && navigator.language || 'es').startsWith('en') ? 'en' : 'es',
    theme: 'auto',
    filters: { hideGround: false, military: false, type: 'all', altBand: 'all', text: '' },
    layers: { trails: true, airports: false, rain: false, sigmet: false },
    notifySpecial: false,
};

function load() {
    try {
        const saved = JSON.parse(localStorage.getItem(KEY)) || {};
        return {
            ...defaults, ...saved,
            filters: { ...defaults.filters, ...saved.filters },
            layers: { ...defaults.layers, ...saved.layers },
        };
    } catch {
        return structuredClone(defaults);
    }
}

export const state = {
    ...load(),
    selected: null, // id del vuelo seleccionado
    follow: false,
    chase: false, // vista 3D en primera persona activa
    mode: 'live', // live | replay
    config: { min_zoom: 6, history: false, receiver: null },
    meta: null, // fuente activa y créditos, llega por el stream
};

export function savePrefs() {
    const { units, lang, theme, filters, layers, notifySpecial } = state;
    try {
        localStorage.setItem(KEY, JSON.stringify({ units, lang, theme, filters, layers, notifySpecial }));
    } catch { /* modo privado o almacenamiento bloqueado: se ignora */ }
}

const listeners = {};
export const on = (event, fn) => (listeners[event] ||= []).push(fn);
export const emit = (event, ...args) => (listeners[event] || []).forEach(fn => fn(...args));

export function resolvedTheme() {
    if (state.theme !== 'auto') return state.theme;
    return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}
