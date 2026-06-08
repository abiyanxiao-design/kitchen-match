const CACHE_NAME = "kitchen-match-v2";
const APP_VERSION = "20260607-v2";
const APP_SHELL = [
  "/",
  "/index.html",
  `/styles.css?v=${APP_VERSION}`,
  `/app.js?v=${APP_VERSION}`,
  `/manifest.json?v=${APP_VERSION}`,
  `/icons/icon-192.png?v=${APP_VERSION}`,
  `/icons/icon-512.png?v=${APP_VERSION}`,
  `/icons/icon-maskable-512.png?v=${APP_VERSION}`,
  `/icons/apple-touch-icon-180.png?v=${APP_VERSION}`,
];

async function networkFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const response = await fetch(request, { cache: "no-store" });
    if (response && response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (_error) {
    const cached = await cache.match(request, { ignoreSearch: false });
    if (cached) {
      return cached;
    }
    if (request.mode === "navigate") {
      return cache.match("/index.html");
    }
    throw _error;
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request, { ignoreSearch: false });
  if (cached) {
    return cached;
  }
  const response = await fetch(request);
  if (response && response.ok) {
    cache.put(request, response.clone());
  }
  return response;
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key)),
      ),
    ),
  );
  self.clients.claim();
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) {
    return;
  }

  const destination = request.destination;
  const isDocument = request.mode === "navigate" || destination === "document";
  const isCodeAsset = destination === "script" || destination === "style" || destination === "manifest";
  const isImage = destination === "image";

  if (isDocument || isCodeAsset) {
    event.respondWith(networkFirst(request));
    return;
  }

  if (isImage) {
    event.respondWith(cacheFirst(request));
    return;
  }

  event.respondWith(networkFirst(request));
});
