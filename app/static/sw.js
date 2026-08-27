// Service worker minimo: cacheia os arquivos estaticos da interface (HTML/CSS/JS)
// para o app abrir instantaneamente e funcionar como app instalado no celular.
// Chamadas de API (/api/...) NUNCA sao cacheadas — sempre buscam dado fresco
// da rede, já que são os seus investimentos reais.
const CACHE = "investimentos-v1";
const ARQUIVOS_ESTATICOS = ["/", "/static/style.css", "/static/app.js", "/static/manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ARQUIVOS_ESTATICOS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((chaves) =>
      Promise.all(chaves.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/")) {
    return; // deixa passar direto pra rede, sem cache
  }

  event.respondWith(
    caches.match(event.request).then((resposta) => {
      const buscaDeRede = fetch(event.request)
        .then((rede) => {
          caches.open(CACHE).then((cache) => cache.put(event.request, rede.clone()));
          return rede;
        })
        .catch(() => resposta);
      return resposta || buscaDeRede;
    })
  );
});
