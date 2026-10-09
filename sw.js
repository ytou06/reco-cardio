// Service worker : l'appli fonctionne hors ligne et se met à jour en arrière-plan.
const CACHE = 'recos-cardio-2026-10-09a';
const SHELL = ['./', './index.html', './data/content.json', './manifest.webmanifest', './icons/icon-192.png', './icons/icon-512.png', './icons/apple-touch-icon.png'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  const fresh = req.mode === 'navigate' || url.pathname.endsWith('/') || url.pathname.endsWith('index.html') || url.pathname.endsWith('content.json');
  if (fresh) {
    // réseau d'abord pour recevoir les mises à jour, cache si hors ligne
    const key = url.pathname.endsWith('content.json') ? './data/content.json' : './index.html';
    e.respondWith(fetch(req).then(r => { if (r.ok) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(key, copy)); } return r; })
      .catch(() => caches.match(key)));
    return;
  }
  // polices et icônes : cache d'abord
  e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(r => {
    if (r.ok || r.type === 'opaque') { const copy = r.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
    return r;
  }).catch(() => hit)));
});
