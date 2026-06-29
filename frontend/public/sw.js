// ═══════════════════════════════════════════════
//  HabboBOTS — Service Worker
//  Maneja push notifications y cache básica
// ═══════════════════════════════════════════════

const CACHE_NAME = 'habbobots-v1';
const CACHE_URLS = ['/', '/offline.html'];

// ── Instalación ───────────────────────────────
self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE_NAME).then(c => c.addAll(CACHE_URLS).catch(() => {}))
  );
});

// ── Activación ────────────────────────────────
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// ── Push notifications ────────────────────────
self.addEventListener('push', e => {
  if (!e.data) return;
  let data = {};
  try { data = e.data.json(); } catch { data = { title: 'HabboBOTS', body: e.data.text() }; }

  const { title = 'HabboBOTS', body = '', url = '/', icon = '/assets/logo.png' } = data;

  e.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon,
      badge: icon,
      data:  { url },
      vibrate: [200, 100, 200],
    })
  );
});

// ── Click en notificación ─────────────────────
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = e.notification.data?.url || '/';
  e.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clients => {
      const match = clients.find(c => c.url.includes(self.location.origin));
      if (match) { match.focus(); match.navigate(url); }
      else self.clients.openWindow(url);
    })
  );
});

// ── Fetch: network-first con fallback cache ───
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  if (e.request.url.includes('/api/')) return; // nunca cachear la API

  e.respondWith(
    fetch(e.request).catch(() =>
      caches.match(e.request).then(r => r || caches.match('/offline.html'))
    )
  );
});
