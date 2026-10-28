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

test('aeronave especial: emergencia > militar > interés > tipo raro', () => {
    assert.equal(m.specialReason({ em: 1, mil: 1 }), 'emergency');
    assert.equal(m.specialReason({ mil: 1 }), 'military');
    assert.equal(m.specialReason({ int: 1 }), 'interesting');
    assert.equal(m.specialReason({ ty: 'A388' }), 'rare');
    assert.equal(m.specialReason({ ty: 'B738' }), null);
});

test('progreso de ruta y ETA', () => {
    const bog = { lat: 4.70, lon: -74.15 }, mde = { lat: 6.16, lon: -75.42 };
    const half = m.routeProgress(bog, mde, 5.43, -74.78, 200);
    assert.ok(half.fraction > 0.45 && half.fraction < 0.55);
    assert.ok(half.etaMin > 5 && half.etaMin < 12);
    assert.equal(m.routeProgress(bog, mde, 5.43, -74.78, 5).etaMin, null);
    assert.equal(m.routeProgress(bog, mde, 6.16, -75.42, 200).fraction, 1);
    assert.equal(m.routeProgress(bog, bog, 4.7, -74.15, 200), null);
});

test('viento: de cara resta velocidad sobre el suelo, de cola la suma', () => {
    const head = m.windComponents(90, 200, 90, 40);  // viento DESDE el este, avión hacia el este
    assert.ok(Math.abs(head.headKt - 40) < 1e-9);
    assert.ok(Math.abs(head.tasKt - (200 * 1.94384 + 40)) < 1e-6);
    const tail = m.windComponents(90, 200, 270, 40);
    assert.ok(Math.abs(tail.headKt + 40) < 1e-9);
    assert.ok(Math.abs(m.windComponents(90, 200, 0, 30).headKt) < 1e-9);  // viento cruzado puro
});

test('pista: línea centrada con la longitud pedida', () => {
    const [a, b] = m.runwayLine({ lat: 4.7, lon: -74.1, length_ft: 12467, le_hdg: 90, he_hdg: 270 });
    assert.ok(a[0] > b[0] && Math.abs(a[1] - b[1]) < 1e-6);
    const km = m.distanceKm(a[1], a[0], b[1], b[0]);
    assert.ok(Math.abs(km - 12467 * 0.0003048) < 0.05);
});
