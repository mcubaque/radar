import { esc } from './util.js';

export function toast(message, { type = 'info', timeout = 6000, onClick } = {}) {
    const el = document.createElement('button');
    el.type = 'button';
    el.className = `toast ${type}`;
    el.innerHTML = esc(message);
    const dismiss = () => el.remove();
    el.addEventListener('click', () => {
        onClick?.();
        dismiss();
    });
    document.getElementById('toasts').appendChild(el);
    setTimeout(dismiss, timeout);
}
