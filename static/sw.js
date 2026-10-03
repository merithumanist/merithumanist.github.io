// Offline reading: pages come from the network when online (always fresh) and are saved
// as you read them; offline, saved pages and images are shown instead.
const CACHE = "merit-v2";
self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(["/", "/logs/", "/explore/"])).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request;
  const u = new URL(req.url);
  if (req.method !== "GET" || u.origin !== location.origin) return;  // stats etc. untouched
  if (/\.(xml|txt)$|^\/google[^/]*\.html$/.test(u.pathname)) return;  // sitemap, feed, robots, verification: always straight from the site
  e.respondWith(fetch(req).then(res => {
    if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
    return res;
  }).catch(() => caches.match(req, {ignoreSearch: true})
    .then(r => r || (req.mode === "navigate" ? caches.match("/") : Response.error()))));
});
