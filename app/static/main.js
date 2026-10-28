const REFRESH_MS = 10000;
const MIN_ZOOM = 6; // más lejos que esto la zona es demasiado grande para pedirla a OpenSky

const map = L.map('map').setView([40.7, -74], 9);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
    maxZoom: 18,
}).addTo(map);

const statusEl = document.getElementById('status');
const markers = new Map(); // icao24 -> L.Marker
let selected = null;
let trackLine = null;
let loading = false;

function setStatus(text, isError = false) {
    statusEl.textContent = text;
    statusEl.classList.toggle('error', isError);
}

function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function planeIcon(f) {
    const cls = 'plane' + (f.on_ground ? ' ground' : '') + (f.icao24 === selected ? ' selected' : '');
    // ✈ apunta a la derecha (90°), así que se resta 90° al rumbo
    const rot = (f.heading ?? 0) - 90;
    return L.divIcon({
        className: '',
        html: `<div class="${cls}" style="transform: rotate(${rot}deg)">✈</div>`,
        iconSize: [22, 22],
        iconAnchor: [11, 11],
    });
}

function popupHtml(f) {
    const kmh = f.velocity != null ? Math.round(f.velocity * 3.6) + ' km/h' : '—';
    const alt = f.altitude != null ? Math.round(f.altitude) + ' m' : '—';
    return `<b>${escapeHtml(f.callsign || 'Sin callsign')}</b> (${escapeHtml(f.icao24)})<br>` +
        `País: ${escapeHtml(f.country ?? '—')}<br>Altitud: ${alt}<br>Velocidad: ${kmh}<br>` +
        `Rumbo: ${f.heading != null ? Math.round(f.heading) + '°' : '—'}`;
}

function render(flights) {
    const alive = new Set();
    for (const f of flights) {
        alive.add(f.icao24);
        let m = markers.get(f.icao24);
        if (m) {
            m.setLatLng([f.latitude, f.longitude]);
            m.setIcon(planeIcon(f));
            m.setPopupContent(popupHtml(f));
        } else {
            m = L.marker([f.latitude, f.longitude], { icon: planeIcon(f) }).addTo(map);
            m.bindPopup(popupHtml(f));
            m.on('click', () => selectFlight(f.icao24));
            markers.set(f.icao24, m);
        }
    }
    for (const [id, m] of markers) {
        if (!alive.has(id)) {
            m.remove();
            markers.delete(id);
        }
    }
}

async function selectFlight(icao24) {
    selected = icao24;
    if (trackLine) { trackLine.remove(); trackLine = null; }
    try {
        const res = await fetch(`/api/track/${encodeURIComponent(icao24)}`);
        const points = await res.json();
        if (selected === icao24 && points.length > 1) {
            trackLine = L.polyline(points, { color: '#d32f2f', weight: 2 }).addTo(map);
        }
    } catch (e) {
        console.error('Error obteniendo trayectoria:', e);
    }
}

async function updateTraffic() {
    if (loading) return;
    if (map.getZoom() < MIN_ZOOM) {
        setStatus('Acerca el mapa para ver vuelos');
        return;
    }
    loading = true;
    const b = map.getBounds();
    const qs = new URLSearchParams({
        lamin: b.getSouth(), lomin: b.getWest(), lamax: b.getNorth(), lomax: b.getEast(),
    });
    try {
        const res = await fetch('/api/flights?' + qs);
        const body = await res.json();
        if (!res.ok) throw new Error(body.error || res.status);
        render(body);
        setStatus(`${body.length} vuelos · ${new Date().toLocaleTimeString()}`);
    } catch (e) {
        setStatus(String(e.message || e), true);
    } finally {
        loading = false;
    }
}

function locate() {
    if (!('geolocation' in navigator)) return setStatus('Geolocalización no disponible', true);
    navigator.geolocation.getCurrentPosition(
        p => map.setView([p.coords.latitude, p.coords.longitude], 9),
        () => setStatus('No se pudo obtener tu ubicación', true),
    );
}

// Búsqueda
const searchEl = document.getElementById('search');
const resultsEl = document.getElementById('results');
let searchTimer;
searchEl.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(async () => {
        const q = searchEl.value.trim();
        resultsEl.replaceChildren();
        if (q.length < 2) return;
        const found = await (await fetch('/api/search?q=' + encodeURIComponent(q))).json();
        for (const f of found) {
            const li = document.createElement('li');
            li.textContent = `${f.callsign || '—'} (${f.icao24})`;
            li.onclick = () => {
                resultsEl.replaceChildren();
                map.setView([f.latitude, f.longitude], 9);
                selectFlight(f.icao24);
            };
            resultsEl.appendChild(li);
        }
        if (!found.length) resultsEl.innerHTML = '<li>Sin resultados (solo vuelos vistos recientemente)</li>';
    }, 300);
});

document.getElementById('locate').addEventListener('click', locate);
map.on('moveend', updateTraffic);
setInterval(updateTraffic, REFRESH_MS);
updateTraffic();
locate();
