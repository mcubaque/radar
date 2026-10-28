import assert from 'node:assert/strict';
import test from 'node:test';

import { RUNWAY_FLOATS_PER_VERTEX as F, runwayMesh } from '../../app/static/js/runwaymesh.js';

// pista este-oeste de ~3,3 km y 148 ft (45 m), como las de Bogotá pero alineada con el este
const RW = { le_lat: 4.70, le_lon: -74.16, he_lat: 4.70, he_lon: -74.13, width_ft: 148 };
const column = (vertices, k) => Array.from({ length: vertices.length / F }, (_, i) => vertices[i * F + k]);
const span = a => Math.max(...a) - Math.min(...a);

test('son triángulos completos centrados en la pista', () => {
    const { lat, lon, vertices } = runwayMesh(RW);
    assert.equal(vertices.length % (F * 3), 0);
    assert.ok(vertices.every(Number.isFinite));
    assert.ok(Math.abs(lat - 4.70) < 1e-9 && Math.abs(lon + 74.145) < 1e-9);
});

test('el asfalto mide el largo y el ancho de la pista, y la pintura queda dentro', () => {
    const { vertices } = runwayMesh(RW);
    const lengthM = 0.03 * 111320 * Math.cos((4.7 * Math.PI) / 180);
    assert.ok(Math.abs(span(column(vertices, 0)) - lengthM) < 1);         // este-oeste: el largo
    assert.ok(Math.abs(span(column(vertices, 1)) - 148 * 0.3048) < 0.5);  // norte-sur: el ancho
});

test('el asfalto es plano y la pintura va justo encima', () => {
    const { vertices } = runwayMesh(RW);
    const heights = new Set(column(vertices, 2).map(z => z.toFixed(3)));
    assert.deepEqual([...heights].sort(), ['0.000', '0.080']);
});

test('sin ancho conocido se usa un ancho por defecto razonable', () => {
    const width = span(column(runwayMesh({ ...RW, width_ft: 0 }).vertices, 1));
    assert.ok(width > 30 && width < 50);
});

test('hay bordes, eje discontinuo y umbrales en ambos extremos', () => {
    const quads = runwayMesh(RW).vertices.length / F / 6;
    assert.ok(quads > 1 + 2 + 50 + 16);  // asfalto + bordes + trazos del eje + barras de umbral
});
