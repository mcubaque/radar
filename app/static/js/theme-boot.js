// Aplica el tema antes de pintar para evitar un destello (script clásico y externo para cumplir la CSP)
try {
    const theme = (JSON.parse(localStorage.getItem('skymonitor.prefs')) || {}).theme || 'auto';
    const dark = theme === 'dark' || (theme === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
} catch (e) { /* sin preferencias guardadas */ }
