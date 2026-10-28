import { state } from './state.js';

const FT = 3.28084;
const KT = 1.94384;
const num = (n, digits = 0) => n.toLocaleString(state.lang, { maximumFractionDigits: digits });
const DASH = '—';

/** Devuelve [principal, secundario] según las unidades elegidas. */
export function altitude(m) {
    if (m == null) return [DASH, ''];
    const ft = `${num(m * FT)} ft`, metric = `${num(m)} m`;
    return state.units === 'aviation' ? [ft, metric] : [metric, ft];
}

export function speed(ms) {
    if (ms == null) return [DASH, ''];
    const kt = `${num(ms * KT)} kt`, kmh = `${num(ms * 3.6)} km/h`;
    return state.units === 'aviation' ? [kt, kmh] : [kmh, kt];
}

export function verticalRate(ms) {
    if (ms == null) return DASH;
    const sign = ms > 0 ? '+' : '';
    return state.units === 'aviation' ? `${sign}${num(ms * 196.85)} ft/min` : `${sign}${num(ms, 1)} m/s`;
}

export function distance(km) {
    return state.units === 'aviation' ? `${num(km / 1.852, 1)} nm` : `${num(km, 1)} km`;
}

export const heading = deg => (deg == null ? DASH : `${Math.round(deg)}°`);
