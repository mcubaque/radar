import assert from 'node:assert/strict';
import test from 'node:test';

import * as m from '../../app/static/js/flightmodel.js';

const NO_FILTERS = { hideGround: false, military: false, type: 'all', altBand: 'all', text: '' };

test('cubeta de altitud: 0 en tierra, creciente con la altura', () => {
    assert.equal(m.altitudeBucket({ gnd: 1 }), 0);
    assert.equal(m.altitudeBucket({ alt: 100 }), 1);
    assert.equal(m.altitudeBucket({ alt: 13000 }), m.ICON_BUCKETS - 1);
});

test('forma del icono según la categoría ADS-B', () => {
    assert.equal(m.shapeFor({ cat: 'A7' }), 'heli');
    assert.equal(m.shapeFor({ cat: 'A1' }), 'light');
    assert.equal(m.shapeFor({}), 'plane');
});

test('filtros', () => {
    assert.equal(m.passes({ gnd: 1 }, { ...NO_FILTERS, hideGround: true }), false);
    assert.equal(m.passes({ cs: 'DAL12' }, { ...NO_FILTERS, text: 'dal' }), true);
    assert.equal(m.passes({ cs: 'UAL1' }, { ...NO_FILTERS, text: 'dal' }), false);
    assert.equal(m.passes({ alt: 5000 }, { ...NO_FILTERS, altBand: 'mid' }), true);
    assert.equal(m.passes({ gnd: 1 }, { ...NO_FILTERS, altBand: 'mid' }), false);
    assert.equal(m.activeFilterCount({ ...NO_FILTERS, hideGround: true, text: 'x' }), 2);
});

test('estimación de posición', () => {
    const [lat, lon] = m.advance(40, -74, 250, 90, 10);
    assert.ok(Math.abs(lat - 40) < 1e-9 && lon > -74, 'hacia el este solo cambia la longitud');
    assert.deepEqual(m.advance(40, -74, 250, 90, 0), [40, -74]);
    assert.deepEqual(m.advance(40, -74, 0, 90, 10), [40, -74]);
    assert.deepEqual(m.advance(40, -74, 250, 0, 600), m.advance(40, -74, 250, 0, m.MAX_EXTRAPOLATE_S));
});

test('círculo de alcance cierra el polígono', () => {
    const ring = m.circlePolygon(0, 0, 100);
    assert.equal(ring.length, 73);
    assert.ok(ring[0].every((n, i) => Math.abs(n - ring[72][i]) < 1e-9));
});

test('altitud de presion: 0 a 1013,25 hPa y coherente con la atmosfera estandar', () => {
    assert.ok(Math.abs(m.pressureAltitude(1013.25)) < 1e-6);
    assert.ok(Math.abs(m.pressureAltitude(898.7) - 1000) < 15);  // ~1000 m
    assert.ok(Math.abs(m.pressureAltitude(226.3) - 11000) < 60);  // tropopausa
});

test('altura sobre el terreno: caso Bogota (presion en superficie 758,5 hPa)', () => {
    const ground = m.pressureAltitude(758.5);  // altitud de presion del suelo, ~2376 m aunque el terreno este a 2547 m
    assert.ok(Math.abs(ground - 2376) < 5);
    assert.equal(m.heightAboveGround(ground, 758.5), 0);  // un avion en pista marca lo mismo que el suelo
    assert.ok(Math.abs(m.heightAboveGround(ground + 300, 758.5) - 300) < 1e-6);
    assert.equal(m.heightAboveGround(ground - 50, 758.5), 0);  // nunca negativa
});
