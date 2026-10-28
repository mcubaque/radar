// Reproducción histórica: revive lo grabado en la zona visible con un control de tiempo.
import { replaceAll } from './flightlayer.js';
import { t } from './i18n.js';
import { bounds } from './map.js';
import { emit, state } from './state.js';
import { stop as stopStream, syncViewport } from './stream.js';
import { toast } from './toast.js';
import { $, debounce, fetchJson } from './util.js';

const bar = document.getElementById('replaybar');
const slider = $('#rp-slider');
let range = null;
let timer = null;

const fmt = ts => new Date(ts * 1000).toLocaleString(state.lang, { dateStyle: 'short', timeStyle: 'medium' });

function showTime(count) {
    $('#rp-time').textContent = fmt(state.replayTime);
    $('#rp-time').dateTime = new Date(state.replayTime * 1000).toISOString();
    slider.value = state.replayTime;
    emit('replay-time', count);
}

export async function loadFrame() {
    if (state.mode !== 'replay') return;
    showTime();
    try {
        const frame = await fetchJson(`/api/replay?${new URLSearchParams({ ...bounds(), t: state.replayTime })}`);
        replaceAll(frame);
        showTime(frame.length);
    } catch (e) {
        toast(e.status === 400 ? t('status.zoom') : e.message, { type: 'error' });
    }
}
export const loadFrameSoon = debounce(loadFrame, 150);

function setPlaying(playing) {
    clearInterval(timer);
    timer = null;
    $('#rp-play').textContent = playing ? '⏸' : '▶';
    if (!playing) return;
    timer = setInterval(() => {
        state.replayTime = Math.min(range.last, state.replayTime + Number($('#rp-speed').value));
        if (state.replayTime >= range.last) setPlaying(false);
        loadFrame();
    }, 1000);
}

async function enter() {
    range = await fetchJson('/api/replay/range').catch(() => null);
    if (!range) return toast(t('replay.empty'), { type: 'error' });
    stopStream();
    state.mode = 'replay';
    state.replayTime = Math.max(range.first, range.last - 600);
    slider.min = range.first;
    slider.max = range.last;
    bar.hidden = false;
    $('#btn-replay').classList.add('active');
    loadFrame();
}

export function exitReplay() {
    if (state.mode !== 'replay') return;
    setPlaying(false);
    state.mode = 'live';
    state.replayTime = null;
    bar.hidden = true;
    $('#btn-replay').classList.remove('active');
    syncViewport();
}

export function bindReplay() {
    $('#btn-replay').addEventListener('click', () => (state.mode === 'replay' ? exitReplay() : enter()));
    $('#rp-live').addEventListener('click', exitReplay);
    $('#rp-play').addEventListener('click', () => {
        if (state.replayTime >= range.last) state.replayTime = range.first;
        setPlaying(!timer);
    });
    slider.addEventListener('input', () => {
        state.replayTime = Number(slider.value);
        showTime();
        loadFrameSoon();
    });
}
