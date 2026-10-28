// Debe coincidir con el @media de style.css: movil, tablet vertical y movil horizontal usan hojas inferiores
export const isCompact = () => matchMedia('(max-width: 900px), (max-height: 500px)').matches;

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ESCAPES[c]);

export function debounce(fn, ms) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), ms);
    };
}

export async function fetchJson(url, options) {
    const res = await fetch(url, options);
    const body = res.status === 204 ? null : await res.json().catch(() => null);
    if (!res.ok) throw Object.assign(new Error(body?.error || res.statusText), { status: res.status });
    return body;
}
