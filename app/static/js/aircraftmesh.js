// Modelos 3D sencillos de aeronaves para la capa WebGL de la vista en primera persona.
// Unidades: el largo del modelo es 1; x a la derecha, y hacia el morro, z hacia arriba. Sin DOM ni WebGL: se puede probar.

export const FLOATS_PER_VERTEX = 9; // posición (3), normal (3), color (3)

export const hexToRgb = hex => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255);

// --- familias: qué modelo usar según el tipo OACI o la categoría ADS-B ---

const TYPES = {
    quad: 'A388 B744 B748 B74S B74R A343 A345 A346 A342 A124 A225 IL96 B52 C5M K35R',
    wide: 'B772 B773 B77L B77W B788 B789 B78X A332 A333 A338 A339 A359 A35K A306 A310 B762 B763 B764 MD11 DC10 L101 IL76 C17 A3ST A337 BLCF',
    turboprop: 'AT43 AT44 AT45 AT46 AT72 AT73 AT75 AT76 DH8A DH8B DH8C DH8D SF34 JS31 JS32 JS41 E120 B190 BE20 BE99 BE9L C208 PC12 AN24 AN26 AN32 F50 F27 D328 SB20 C130 A400 DHC6 DHC7 C212 CN35 PC6T TBM9 TBM8 P46T',
    biz: 'GLF2 GLF3 GLF4 GLF5 GLF6 GL5T GL7T GLEX C25A C25B C25C C25M C510 C525 C550 C560 C56X C680 C68A C700 C750 CL30 CL35 CL60 E50P E55P FA7X FA8X FA50 FA20 LJ35 LJ45 LJ60 LJ75 H25B H25C PRM1 SF50 EA50 HDJT',
    light: 'C172 C182 C152 C150 C170 C177 C206 C210 P28A P28R P32R PA34 PA44 PA46 SR20 SR22 BE35 BE36 BE33 BE58 DA40 DA42 DA62 M20P M20T RV7 RV8 AA5 C140 PC7',
    heli: 'R22 R44 R66 B06 B407 B412 B429 EC35 EC45 EC30 AS50 AS55 AS65 H60 UH1 S76 S92 A109 A139 AW09 MD52 MD60',
};
const TYPE_FAMILY = new Map(Object.entries(TYPES).flatMap(([family, list]) => list.split(' ').map(code => [code, family])));
const CATEGORY_FAMILY = { A1: 'light', B1: 'light', A5: 'wide', A7: 'heli' };

/** Familia de modelo ('narrow' por defecto) de un vuelo según su tipo OACI y su categoría ADS-B. */
export const familyFor = f => TYPE_FAMILY.get(f.ty) ?? CATEGORY_FAMILY[f.cat] ?? 'narrow';

/** Largo aproximado en metros de cada familia: el modelo se dibuja a este tamaño real. */
export const FAMILY_LENGTH_M = { narrow: 38, wide: 62, quad: 72, turboprop: 27, biz: 20, light: 8.5, heli: 13 };

// Color de cola por aerolínea (prefijo OACI del callsign); sin dato se usa el color de altitud
const LIVERY = {
    AVA: '#d71920', ARE: '#1b2a7a', LAN: '#1c2f7a', LPE: '#1c2f7a', LXP: '#1c2f7a', TAM: '#c8102e', JBU: '#0a4aa6',
    VVC: '#f8a000', EFY: '#f7941d', SKU: '#e30613', DAL: '#c01933', AAL: '#6b7280', UAL: '#0033a0', IBE: '#d7192d',
    AFR: '#002157', KLM: '#00a1de', UAE: '#d71a21', DLH: '#05164d', BAW: '#075aaa', CMP: '#0072ce', FDX: '#4d148c',
    UPS: '#4a2c1a', RYR: '#073590', EZY: '#ff6600', QTR: '#5c0632', THY: '#c8102e', ACA: '#f01428', AMX: '#0b2265',
    VOI: '#00a3e0', SWA: '#304cb2', NKS: '#ffd200', PUE: '#1e3a8a', GLG: '#f26522', ARG: '#0b5fa5', AZU: '#0057a8',
};

/** Color de cola de la aerolínea de un callsign (p. ej. 'AVA9411'), o null si no se conoce. */
export const liveryColor = callsign => LIVERY[(callsign || '').slice(0, 3).toUpperCase()] ?? null;

// --- primitivas ---

const AXES = { z: (a, b, c) => [a, b, c], x: (a, b, c) => [c, a, b], y: (a, b, c) => [a, c, b] };
const signedArea = poly => poly.reduce((sum, [x1, y1], i) => {
    const [x2, y2] = poly[(i + 1) % poly.length];
    return sum + (x1 * y2 - x2 * y1) / 2;
}, 0);
const normalize = v => { const l = Math.hypot(...v) || 1; return v.map(c => c / l); };

/**
 * Prisma de un polígono convexo extruido entre `lo` y `hi`. El polígono vive en los dos ejes de `axis` y se extruye
 * en el tercero: 'z' (vista desde arriba), 'x' (perfil: ejes y, z) o 'y' (vista frontal: ejes x, z).
 */
export function prism(poly, lo, hi, rgb, axis = 'z') {
    const map = AXES[axis];
    const ring = signedArea(poly) > 0 ? [...poly].reverse() : poly;  // las normales laterales suponen sentido horario
    const out = [];
    const push = (a, b, c, n) => out.push(...map(a, b, c), ...map(...n), ...rgb);
    for (const [c, nz] of [[hi, 1], [lo, -1]]) {
        for (let i = 1; i < ring.length - 1; i++) for (const k of [0, i, i + 1]) push(ring[k][0], ring[k][1], c, [0, 0, nz]);
    }
    for (let i = 0; i < ring.length; i++) {
        const [ax, ay] = ring[i], [bx, by] = ring[(i + 1) % ring.length];
        const len = Math.hypot(bx - ax, by - ay) || 1;
        const n = [-(by - ay) / len, (bx - ax) / len, 0];
        for (const [a, b, c] of [[ax, ay, lo], [bx, by, lo], [bx, by, hi], [ax, ay, lo], [bx, by, hi], [ax, ay, hi]]) push(a, b, c, n);
    }
    return out;
}

export const extrude = (poly, z0, z1, rgb) => prism(poly, z0, z1, rgb, 'z');
const box = (cx, cy, cz, sx, sy, sz, rgb) => prism([[cx - sx / 2, cy - sy / 2], [cx + sx / 2, cy - sy / 2], [cx + sx / 2, cy + sy / 2], [cx - sx / 2, cy + sy / 2]], cz - sz / 2, cz + sz / 2, rgb);

/**
 * Tubo a lo largo del eje y que pasa por las secciones {y, rx, rz, cz, x}: fuselajes, góndolas y bocas de motor.
 * `color(sección, ángulo)` permite pintar ventanas y parabrisas.
 */
export function loft(sections, color, segments = 24) {
    const out = [];
    const ring = (s, i) => Array.from({ length: segments }, (_, k) => {
        const t = (2 * Math.PI * k) / segments;
        const n = normalize([Math.cos(t) * s.rz, 0, Math.sin(t) * s.rx]);
        return { p: [(s.x ?? 0) + s.rx * Math.cos(t), s.y, s.cz + s.rz * Math.sin(t)], n, rgb: color(i, t) };
    });
    const rings = sections.map(ring);
    const push = v => out.push(...v.p, ...v.n, ...v.rgb);
    for (let i = 0; i < rings.length - 1; i++) {
        for (let k = 0; k < segments; k++) {
            const a = rings[i][k], b = rings[i][(k + 1) % segments], c = rings[i + 1][k], d = rings[i + 1][(k + 1) % segments];
            [a, b, d, a, d, c].forEach(push);
        }
    }
    for (const [idx, ny] of [[0, 1], [rings.length - 1, -1]]) {  // tapas planas en los extremos
        const s = sections[idx], center = { p: [s.x ?? 0, s.y, s.cz], n: [0, ny, 0], rgb: rings[idx][0].rgb };
        for (let k = 0; k < segments; k++) [center, rings[idx][k], rings[idx][(k + 1) % segments]].forEach(v => push({ ...v, n: [0, ny, 0] }));
    }
    return out;
}

const mirrorX = poly => poly.map(([x, y]) => [-x, y]);
const sym = (poly, lo, hi, rgb, axis = 'z') => [...prism(poly, lo, hi, rgb, axis), ...prism(mirrorX(poly), lo, hi, rgb, axis)];

// --- piezas de aeronave ---

const WINDOW = '#27303f';

/** Fuselaje de sección elíptica: morro redondeado, parte central constante y cola que se afina y sube. */
function fuselage({ r, noseLen = 0.1, tailLen = 0.22, rise = 0.5, y0 = -0.5, y1 = 0.5 }, body, glass = WINDOW) {
    const bodyRgb = hexToRgb(body), dark = hexToRgb(glass);
    const sections = [
        { y: y1, f: 0.06, up: 0 }, { y: y1 - noseLen * 0.35, f: 0.5, up: 0 }, { y: y1 - noseLen * 0.8, f: 0.88, up: 0 },
        { y: y1 - noseLen, f: 1, up: 0 }, { y: y0 + tailLen + 0.1, f: 1, up: 0 }, { y: y0 + tailLen, f: 0.92, up: 0.1 * rise },
        { y: y0 + tailLen * 0.5, f: 0.6, up: 0.4 * rise }, { y: y0, f: 0.12, up: rise },
    ].map(s => ({ y: s.y, rx: r * s.f, rz: r * s.f, cz: r + s.up * r * 1.6 }));
    const color = (i, t) => {
        const side = Math.abs(Math.cos(t)) > 0.92, top = Math.sin(t);
        if (i >= 1 && i <= 3 && top > 0.25 && top < 0.95) return dark;                      // parabrisas
        if (i >= 3 && i <= 5 && side && top > 0.1 && top < 0.5) return dark;                // ventanillas de la cabina
        return bodyRgb;
    };
    return loft(sections, color);
}

const nacelle = (x, y, z, r, len, color, spinner = true) => loft([
    { y: y + len / 2, rx: r * 0.8, rz: r * 0.8, cz: z, x },
    { y: y + len * 0.35, rx: r, rz: r, cz: z, x },
    { y: y - len * 0.4, rx: r * 0.95, rz: r * 0.95, cz: z, x },
    { y: y - len / 2, rx: spinner ? r * 0.4 : r * 0.7, rz: spinner ? r * 0.4 : r * 0.7, cz: z, x },
], () => color, 16);

function airliner(c, colors) {
    const wing = hexToRgb(colors.wing), accent = hexToRgb(colors.accent);
    const r = c.r, wz = c.highWing ? r * 1.7 : r * 0.55, tipX = c.span / 2, rootX = r * 0.7;
    const leRoot = c.wingY + 0.07, leTip = leRoot - c.sweep;
    const wingPoly = [[rootX, leRoot], [tipX, leTip], [tipX, leTip - 0.045], [rootX, c.wingY - 0.1]];
    const parts = [...fuselage({ r, noseLen: c.noseLen ?? 0.11, tailLen: c.tailLen ?? 0.24 }, colors.body), ...sym(wingPoly, wz, wz + 0.016, wing)];
    for (const [ex, ey] of c.engines) {
        for (const sx of [-1, 1]) {
            const x = sx * ex;
            parts.push(...nacelle(x, ey, Math.max(c.engineR, wz - c.engineR * 0.9), c.engineR, c.engineLen, accent, false));
            parts.push(...box(x, ey - 0.02, wz - c.engineR * 0.3, 0.012, 0.09, c.engineR * 0.7, wing));  // pilón
        }
    }
    if (c.rearEngines) {
        for (const sx of [-1, 1]) parts.push(...nacelle(sx * (r + c.engineR * 1.1), -0.3, r * 1.45, c.engineR, c.engineLen, accent, false));
    }
    if (c.winglet) {
        const profile = [[leTip, wz], [leTip - 0.045, wz], [leTip - 0.05, wz + 0.055], [leTip - 0.03, wz + 0.055]];
        for (const sx of [-1, 1]) parts.push(...prism(profile, sx * tipX - 0.004, sx * tipX + 0.004, accent, 'x'));
    }
    // cola: deriva en perfil y plano horizontal
    const top = r * 2;
    const fin = [[-0.28, top * 0.9], [-0.42, top + c.finH], [-0.5, top + c.finH], [-0.5, top * 0.9]];
    parts.push(...prism(fin, -0.009, 0.009, accent, 'x'));
    const stabZ = c.ttail ? top + c.finH - 0.012 : r * 1.55;
    const stab = [[0.02, -0.38], [c.stabSpan / 2, -0.45], [c.stabSpan / 2, -0.5], [0.02, -0.5]];
    parts.push(...sym(stab, stabZ, stabZ + 0.012, wing));
    return parts;
}

function turboprop(colors) {
    const wing = hexToRgb(colors.wing), accent = hexToRgb(colors.accent), dark = hexToRgb('#1f2937');
    const r = 0.058, wz = r * 1.75;
    const parts = [...fuselage({ r, noseLen: 0.1, tailLen: 0.26 }, colors.body)];
    parts.push(...sym([[r * 0.7, 0.12], [0.5, 0.12], [0.5, -0.04], [r * 0.7, -0.08]], wz, wz + 0.02, wing));
    for (const sx of [-1, 1]) {
        const x = sx * 0.2;
        parts.push(...nacelle(x, 0.08, wz - 0.03, 0.036, 0.3, accent));
        for (const [w, h] of [[0.16, 0.012], [0.012, 0.16]]) parts.push(...box(x, 0.25, wz - 0.03, w, 0.006, h, dark));  // hélice
    }
    const top = r * 2;
    parts.push(...prism([[-0.3, top * 0.9], [-0.42, top + 0.16], [-0.5, top + 0.16], [-0.5, top * 0.9]], -0.01, 0.01, accent, 'x'));
    parts.push(...sym([[0.01, -0.4], [0.17, -0.45], [0.17, -0.5], [0.01, -0.5]], top + 0.15, top + 0.162, wing));  // cola en T
    return parts;
}

function light(colors) {
    const wing = hexToRgb(colors.wing), accent = hexToRgb(colors.accent), dark = hexToRgb('#1f2937');
    const r = 0.085, wz = r * 1.9;
    const parts = [...fuselage({ r, noseLen: 0.16, tailLen: 0.4 }, colors.body)];
    parts.push(...prism([[-0.65, 0.17], [0.65, 0.17], [0.65, -0.03], [-0.65, -0.03]], wz, wz + 0.025, wing));
    parts.push(...box(0, 0.51, r, 0.5, 0.012, 0.045, dark));  // hélice
    parts.push(...prism([[-0.3, r * 2], [-0.44, r * 2 + 0.2], [-0.5, r * 2 + 0.2], [-0.5, r * 2]], -0.012, 0.012, accent, 'x'));
    parts.push(...sym([[0.01, -0.4], [0.22, -0.44], [0.22, -0.5], [0.01, -0.5]], r * 1.55, r * 1.55 + 0.02, wing));
    return parts;
}

function heli(colors) {
    const accent = hexToRgb(colors.accent), dark = hexToRgb('#1f2937'), wing = hexToRgb(colors.wing);
    const body = hexToRgb(colors.body);
    const parts = loft([
        { y: 0.5, rx: 0.02, rz: 0.03, cz: 0.12 }, { y: 0.4, rx: 0.1, rz: 0.12, cz: 0.14 }, { y: 0.1, rx: 0.13, rz: 0.15, cz: 0.17 },
        { y: -0.1, rx: 0.1, rz: 0.12, cz: 0.17 }, { y: -0.2, rx: 0.04, rz: 0.05, cz: 0.2 },
    ], (i, t) => (i <= 2 && Math.sin(t) > 0.2 && i >= 1 ? hexToRgb(WINDOW) : body), 20);
    parts.push(...loft([{ y: -0.2, rx: 0.025, rz: 0.03, cz: 0.2 }, { y: -0.5, rx: 0.012, rz: 0.02, cz: 0.24 }], () => body, 12));
    parts.push(...box(0, -0.48, 0.3, 0.012, 0.07, 0.12, accent));  // deriva
    parts.push(...box(0, 0.0, 0.34, 0.95, 0.03, 0.008, dark), ...box(0, 0.0, 0.34, 0.03, 0.95, 0.008, dark));  // rotor principal
    parts.push(...box(0.03, -0.5, 0.26, 0.012, 0.16, 0.012, dark));  // rotor de cola
    parts.push(...box(-0.09, 0.05, 0.02, 0.012, 0.5, 0.012, wing), ...box(0.09, 0.05, 0.02, 0.012, 0.5, 0.012, wing));  // patines
    return parts;
}

const AIRLINERS = {
    narrow: { r: 0.052, wingY: 0.02, span: 0.92, sweep: 0.17, engines: [[0.17, 0.09]], engineR: 0.03, engineLen: 0.1, winglet: true, finH: 0.14, stabSpan: 0.36 },
    wide: { r: 0.06, wingY: 0.0, span: 0.98, sweep: 0.2, engines: [[0.2, 0.1]], engineR: 0.046, engineLen: 0.14, winglet: false, finH: 0.15, stabSpan: 0.38 },
    quad: { r: 0.064, wingY: 0.02, span: 0.9, sweep: 0.2, engines: [[0.15, 0.12], [0.3, 0.06]], engineR: 0.038, engineLen: 0.12, winglet: true, finH: 0.15, stabSpan: 0.36 },
    biz: { r: 0.06, wingY: 0.05, span: 0.78, sweep: 0.14, engines: [], engineR: 0.032, engineLen: 0.14, rearEngines: true, ttail: true, winglet: true, finH: 0.17, stabSpan: 0.3, noseLen: 0.18, tailLen: 0.3 },
};

/**
 * Malla de una familia ('narrow', 'wide', 'quad', 'turboprop', 'biz', 'light' o 'heli').
 * `colors`: body (fuselaje), wing (alas) y accent (cola, motores) como #rrggbb.
 */
export function aircraftMesh(family = 'narrow', colors = {}) {
    const palette = { body: '#f1f5f9', wing: '#cbd5e1', accent: '#2f80ed', ...colors };
    let vertices;
    if (family === 'turboprop') vertices = turboprop(palette);
    else if (family === 'light') vertices = light(palette);
    else if (family === 'heli') vertices = heli(palette);
    else vertices = airliner(AIRLINERS[family] ?? AIRLINERS.narrow, palette);
    return new Float32Array(vertices);
}
