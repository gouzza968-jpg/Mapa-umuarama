// Service worker do Mapa Umuarama
// A versão abaixo é preenchida automaticamente pelo build.py — cada versão nova cria um cache novo.
const VERSION = '/*VERSION*/';
const CACHE = 'mapa-umuarama-' + VERSION;
const ASSETS = ['./', './index.html', './data/mapa.json?v=' + VERSION, './manifest.webmanifest', './icons/icon-192.png', './icons/icon-512.png', './icons/icon-180.png'];

self.addEventListener('install', e => {
  // não ativa sozinho: o usuário escolhe "Atualizar agora" em Configurações
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('mapa-umuarama-') && k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('message', e => { if (e.data === 'skipWaiting') self.skipWaiting(); });

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  // version.json sempre da internet (para saber se há atualização)
  if (url.pathname.endsWith('/version.json')) {
    e.respondWith(fetch(e.request).catch(() => caches.match('./version.json')));
    return;
  }
  // páginas: cache primeiro (funciona offline), internet se não tiver
  e.respondWith(
    caches.match(e.request, {ignoreSearch: url.pathname.endsWith('.html') || url.pathname.endsWith('/')})
      .then(r => r || fetch(e.request))
  );
});
