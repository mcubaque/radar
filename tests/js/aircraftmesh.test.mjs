import assert from 'node:assert/strict';
import test from 'node:test';

import {
    FAMILY_LENGTH_M, FLOATS_PER_VERTEX as F, aircraftMesh, extrude, familyFor, hexToRgb, liveryColor, loft,
} from '../../app/static/js/aircraftmesh.js';

const FAMILIES = Object.keys(FAMILY_LENGTH_M);
const axis = (mesh, k) => Array.from({ length: mesh.length / F }, (_, i) => mesh[i * F + k]);
const span = a => Math.max(...a) - Math.min(...a);

test('color hexadecimal a RGB 0..1', () => {
    assert.deepEqual(hexToRgb('#ff0000'), [1, 0, 0]);
    assert.ok(Math.abs(hexToRgb('#808080')[0] - 128 / 255) < 1e-9);
});

test('familia según tipo OACI y, si no se conoce, la categoría ADS-B', () => {
    assert.equal(familyFor({ ty: 'A320' }), 'narrow');
    assert.equal(familyFor({ ty: 'A388' }), 'quad');
    assert.equal(familyFor({ ty: 'B789' }), 'wide');
    assert.equal(familyFor({ ty: 'AT72' }), 'turboprop');
    assert.equal(familyFor({ ty: 'GLF5' }), 'biz');
    assert.equal(familyFor({ ty: 'C172' }), 'light');
    assert.equal(familyFor({ ty: 'EC35' }), 'heli');
    assert.equal(familyFor({ cat: 'A7' }), 'heli');
    assert.equal(familyFor({ cat: 'A5' }), 'wide');
    assert.equal(familyFor({}), 'narrow');
    assert.equal(familyFor({ ty: 'C208' }), 'turboprop');
});

test('librea: color de cola por aerolínea y nada si no se conoce', () => {
    assert.equal(liveryColor('AVA9411'), '#d71920');
    assert.equal(liveryColor('ava1'), '#d71920');
    assert.equal(liveryColor('HK4541'), null);
    assert.equal(liveryColor(undefined), null);
});

for (const family of FAMILIES) {
    test(`modelo ${family}: triángulos completos, números finitos y normales unitarias`, () => {
        const mesh = aircraftMesh(family);
        assert.ok(mesh.length > 0 && mesh.length % (F * 3) === 0);
        assert.ok(mesh.every(Number.isFinite));
        for (let i = 0; i < mesh.length; i += F) assert.ok(Math.abs(Math.hypot(mesh[i + 3], mesh[i + 4], mesh[i + 5]) - 1) < 1e-6);
    });

    test(`modelo ${family}: cabe en un cubo de ~1 y descansa sobre z = 0`, () => {
        const mesh = aircraftMesh(family);
        const [x, y, z] = [0, 1, 2].map(k => axis(mesh, k));
        assert.ok(span(y) > 0.85 && span(y) < 1.15, `largo ${span(y)}`);
        assert.ok(span(x) > 0.15 && span(x) < 1.5, `ancho ${span(x)}`);
        if (family !== 'heli') assert.ok(Math.abs(Math.min(...z)) < 0.02);
        assert.ok(Math.max(...z) > 0.1);
    });
}

test('el color de cola solo cambia parte de los vértices y no la geometría', () => {
    const blue = aircraftMesh('narrow', { accent: '#2f80ed' }), red = aircraftMesh('narrow', { accent: '#d71920' });
    let recolored = 0;
    for (let i = 0; i < blue.length; i += F) {
        assert.deepEqual(blue.slice(i, i + 6), red.slice(i, i + 6));  // posición y normal iguales
        if (blue[i + 6] !== red[i + 6]) recolored++;
    }
    const share = recolored / (blue.length / F);
    assert.ok(share > 0.03 && share < 0.5, `parte recoloreada ${share}`);
});

test('las normales laterales apuntan hacia fuera del prisma, sin importar el sentido del polígono', () => {
    for (const square of [[[-1, 1], [1, 1], [1, -1], [-1, -1]], [[-1, -1], [1, -1], [1, 1], [-1, 1]]]) {
        const tri = extrude(square, 0, 1, [1, 1, 1]);
        for (let i = 0; i < tri.length; i += F) {
            const [x, y, , nx, ny] = tri.slice(i, i + F);
            if (nx !== 0 || ny !== 0) assert.ok(x * nx + y * ny > 0);
        }
    }
});

test('un tubo cerrado tiene tapas y las normales apuntan hacia fuera del eje', () => {
    const tube = loft([{ y: 1, rx: 1, rz: 1, cz: 0 }, { y: 0, rx: 1, rz: 1, cz: 0 }], () => [1, 1, 1], 8);
    assert.equal(tube.length / F, 8 * 6 + 2 * 8 * 3);
    for (let i = 0; i < tube.length; i += F) {
        const [x, , z, nx, ny, nz] = tube.slice(i, i + F);
        if (ny === 0) assert.ok(x * nx + z * nz > 0.9);
    }
});
