// Geometría plana de una pista (asfalto, bordes, eje discontinuo y umbrales) en metros alrededor de su centro.
// Sin DOM ni WebGL: se puede probar. La capa WebGL la sitúa a una altura fija para que no siga el ruido del relieve.

export const RUNWAY_FLOATS_PER_VERTEX = 6; // posición (3), color (3)

const ASPHALT = [0.2, 0.21, 0.24];
const PAINT = [0.96, 0.97, 0.98];
const DEFAULT_WIDTH_M = 40;
const FT_M = 0.3048;
const MARKING_LIFT_M = 0.08;  // la pintura va apenas por encima del asfalto

/**
 * Triángulos de una pista a partir de sus dos extremos y su ancho en pies.
 * Devuelve {lat, lon, vertices}: el centro y un Float32Array con x (este), y (norte), z (arriba) y color por vértice.
 */
export function runwayMesh(rw) {
    const lat = (rw.le_lat + rw.he_lat) / 2, lon = (rw.le_lon + rw.he_lon) / 2;
    const kx = 111320 * Math.cos((lat * Math.PI) / 180);
    const dx = (rw.he_lon - rw.le_lon) * kx, dy = (rw.he_lat - rw.le_lat) * 111320;
    const length = Math.hypot(dx, dy) || 1;
    const width = rw.width_ft ? rw.width_ft * FT_M : DEFAULT_WIDTH_M;
    const [ux, uy] = [dx / length, dy / length];   // a lo largo de la pista
    const [px, py] = [-uy, ux];                    // a lo ancho
    const out = [];

    /** Rectángulo centrado en (along, across) metros del centro de la pista, a la altura z. */
    const quad = (along, across, halfLength, halfWidth, z, rgb) => {
        const corner = (a, c) => [ux * a + px * c, uy * a + py * c, z];
        const [p0, p1, p2, p3] = [
            corner(along - halfLength, across - halfWidth), corner(along + halfLength, across - halfWidth),
            corner(along + halfLength, across + halfWidth), corner(along - halfLength, across + halfWidth),
        ];
        for (const p of [p0, p1, p2, p0, p2, p3]) out.push(...p, ...rgb);
    };

    quad(0, 0, length / 2, width / 2, 0, ASPHALT);
    const z = MARKING_LIFT_M;
    for (const side of [-1, 1]) quad(0, side * (width / 2 - 0.6), length / 2 - 4, 0.25, z, PAINT);          // bordes
    for (let a = -length / 2 + 60; a + 30 < length / 2 - 60; a += 50) quad(a + 15, 0, 15, 0.45, z, PAINT);   // eje discontinuo
    for (const end of [-1, 1]) {                                                                              // umbrales
        for (let k = -4; k <= 4; k++) if (k !== 0) quad(end * (length / 2 - 21), (k * width) / 10, 15, 0.9, z, PAINT);
    }
    return { lat, lon, vertices: new Float32Array(out) };
}
