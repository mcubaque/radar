// Lógica pura de vuelos (sin DOM): iconos, colores, filtros y estimación de posición.

export const MAX_EXTRAPOLATE_S = 60;

// Color por altitud (m), de bajo a alto
export const ALT_STEPS = [300, 900, 1500, 3000, 6000, 9000, 12000];
export const ALT_COLORS = ['#ffd400', '#ffb000', '#9bd600', '#19c37d', '#12b5cb', '#2f80ed', '#7b61ff', '#d63af9'];
export const GROUND_COLOR = '#8a8f98';
export const ICON_SHAPES = ['plane', 'light', 'heli'];
export const ICON_BUCKETS = ALT_COLORS.length + 1; // 0 = en tierra

export function altitudeBucket(f) {
    if (f.gnd || f.alt == null) return 0;
    return 1 + ALT_STEPS.filter(step => f.alt >= step).length;
}

export function bucketColor(bucket) {
    return bucket === 0 ? GROUND_COLOR : ALT_COLORS[bucket - 1];
}

export function shapeFor(f) {
    if (f.cat === 'A7') return 'heli';
    if (f.cat === 'A1') return 'light';
    return 'plane';
}

export const iconName = f => `${shapeFor(f)}-${altitudeBucket(f)}`;

const ALT_BANDS = { low: [0, 3000], mid: [3000, 9000], high: [9000, Infinity] };

/** ¿Pasa el vuelo los filtros activos? */
export function passes(f, filters) {
    if (filters.hideGround && f.gnd) return false;
    if (filters.military && !f.mil) return false;
    if (filters.type !== 'all' && shapeFor(f) !== filters.type) return false;
    if (filters.altBand !== 'all') {
        const [min, max] = ALT_BANDS[filters.altBand];
        if (f.gnd || f.alt == null || f.alt < min || f.alt >= max) return false;
    }
    const text = filters.text.trim().toLowerCase();
    if (text && !(f.cs || '').toLowerCase().startsWith(text) && !(f.reg || '').toLowerCase().startsWith(text)) return false;
    return true;
}

export function activeFilterCount(filters) {
    return [filters.hideGround, filters.military, filters.type !== 'all', filters.altBand !== 'all', filters.text.trim()]
        .filter(Boolean).length;
}

/** Posición tras `seconds` segundos avanzando en línea recta con la velocidad y rumbo del vuelo. */
export function advance(lat, lon, speed, heading, seconds) {
    if (!speed || heading == null || seconds <= 0) return [lat, lon];
    const d = speed * Math.min(seconds, MAX_EXTRAPOLATE_S);
    const rad = heading * Math.PI / 180;
    return [
        lat + (d * Math.cos(rad)) / 111320,
        lon + (d * Math.sin(rad)) / (111320 * Math.cos(lat * Math.PI / 180)),
    ];
}

/** Altitud (m) que corresponde a una presion en la atmosfera estandar. */
export const pressureAltitude = hpa => 44330.77 * (1 - (hpa / 1013.25) ** 0.190263);

// Por encima de esto la altura sobre el terreno ya no interesa (y la presion en superficie no la describe bien)
export const MAX_AGL_ALT_M = 6000;

/** Altura sobre el terreno (m): altitud barometrica menos la altitud de presion del suelo bajo el avion. */
export const heightAboveGround = (baroAlt, surfaceHpa) => Math.max(0, baroAlt - pressureAltitude(surfaceHpa));

export function emergencyLabel(f) {
    return { 7500: 'hijack', 7600: 'radio', 7700: 'general' }[f.sq] || 'general';
}

/** Puntos de un círculo (para anillos de alcance del receptor propio). */
export function circlePolygon(lat, lon, radiusKm, steps = 72) {
    const coords = [];
    for (let i = 0; i <= steps; i++) {
        const bearing = (i / steps) * 2 * Math.PI;
        const dLat = (radiusKm / 6371) * Math.cos(bearing);
        const dLon = (radiusKm / 6371) * Math.sin(bearing) / Math.cos(lat * Math.PI / 180);
        coords.push([lon + dLon * 180 / Math.PI, lat + dLat * 180 / Math.PI]);
    }
    return coords;
}

// --- aeronaves especiales ---

// Tipos OACI poco comunes o llamativos para aficionados
export const RARE_TYPES = new Set([
    'A388', 'A225', 'A124', 'B748', 'A3ST', 'A337', 'BLCF', 'B52', 'C5M', 'C17', 'E3TF', 'K35R', 'V22', 'A400',
    'IL76', 'AN12', 'B703', 'CONC', 'DC3', 'DC6', 'C130', 'E6', 'B2', 'F22', 'F35',
]);

/** Por qué un vuelo es especial ('emergency' | 'military' | 'interesting' | 'rare') o null. */
export function specialReason(f) {
    if (f.em) return 'emergency';
    if (f.mil) return 'military';
    if (f.int) return 'interesting';
    if (RARE_TYPES.has(f.ty)) return 'rare';
    return null;
}

// --- ruta, ETA y viento ---

const R_KM = 6371;
const rad = d => (d * Math.PI) / 180;

export function distanceKm(lat1, lon1, lat2, lon2) {
    const a = Math.sin(rad(lat2 - lat1) / 2) ** 2
        + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lon2 - lon1) / 2) ** 2;
    return 2 * R_KM * Math.asin(Math.min(1, Math.sqrt(a)));
}

/** Avance del vuelo entre origen y destino: {fraction 0..1, remainingKm, etaMin|null}. */
export function routeProgress(origin, destination, lat, lon, speedMs) {
    const total = distanceKm(origin.lat, origin.lon, destination.lat, destination.lon);
    const remaining = distanceKm(lat, lon, destination.lat, destination.lon);
    if (!total) return null;
    const fraction = Math.min(1, Math.max(0, 1 - remaining / total));
    // por debajo de ~100 km/h no hay estimación fiable (rodaje o parado)
    const etaMin = speedMs > 28 ? Math.round(remaining / (speedMs * 3.6) * 60) : null;
    return { fraction, remainingKm: remaining, etaMin };
}

/**
 * Efecto del viento: `headKt` > 0 es viento de cara, < 0 de cola; `tasKt` es la velocidad aerodinámica estimada.
 * El viento sopla DESDE `windDir`.
 */
export function windComponents(trackDeg, groundSpeedMs, windDir, windKt) {
    const gsKt = groundSpeedMs * 1.94384;
    const angle = rad(windDir - trackDeg);
    const headKt = windKt * Math.cos(angle);
    const crossKt = windKt * Math.sin(angle);
    return { headKt, crossKt, tasKt: Math.hypot(gsKt + headKt, crossKt) };
}

/** Extremos [lon, lat] de una pista: su centro desplazado media longitud hacia cada cabecera. */
export function runwayLine(rw) {
    const half = (rw.length_ft || 3000) * 0.3048 / 2;
    const end = hdg => advance(rw.lat, rw.lon, half, hdg, 1).reverse();
    return [end(rw.le_hdg), end(rw.he_hdg)];
}
