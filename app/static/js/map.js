import { resolvedTheme } from './state.js';

const STYLES = {
    light: 'https://tiles.openfreemap.org/styles/positron',
    dark: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
};

export let map;
const styleHandlers = [];

/** Registra una función que debe ejecutarse cada vez que el estilo base (re)carga: setStyle borra capas y fuentes. */
export const onStyleReady = fn => styleHandlers.push(fn);

export function initMap({ lat, lon, zoom }) {
    map = new maplibregl.Map({
        container: 'map',
        style: STYLES[resolvedTheme()],
        center: [lon, lat],
        zoom,
        minZoom: 2,
        maxPitch: 0,
        dragRotate: false,
        attributionControl: false,
    });
    map.touchZoomRotate.disableRotation();
    map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: 'Vuelos: adsb.lol · adsb.fi' }));
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
    map.on('style.load', () => styleHandlers.forEach(fn => fn()));
    return map;
}

// diff: false fuerza recargar todo el estilo; así se dispara style.load y se vuelven a crear nuestras capas
export const setBasemap = theme => map.setStyle(STYLES[theme], { diff: false });

export function bounds() {
    const b = map.getBounds();
    return {
        lamin: Math.max(-90, b.getSouth()), lomin: Math.max(-180, b.getWest()),
        lamax: Math.min(90, b.getNorth()), lomax: Math.min(180, b.getEast()),
    };
}
