// Service Worker: PWA 离线缓存(界面壳)
// 说明:
//   - 只缓存静态界面资源(html/css/js/svg/manifest),API 请求(/__proxy/* 或 8898/8899)不走缓存,
//     实时打到后端,后端离线时由页面提示。
//   - install 时缓存核心壳,activate 时清旧缓存,fetch 时 API 直连、壳走缓存(缓存优先,网络兜底)。

const CACHE = "audio-models-shell-v1";
const CORE = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icon.svg",
  "./config.js",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return; // POST 等 API 一律直连,不拦截

  const url = new URL(req.url);
  // API 端点(代理或直连)与上传类请求 → 直连后端
  const isApi =
    req.mode === "navigate" ? false :
    (url.pathname.startsWith("/__proxy/") ||
     url.port === "8898" || url.port === "8899");
  if (isApi) return; // 不缓存、不拦截,直接放行到网络

  // 界面壳:缓存优先,取不到才走网络,并把网络结果回写缓存(运行中更新)
  e.respondWith(
    caches.match(req, { ignoreSearch: true }).then((hit) => {
      const network = fetch(req).then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      }).catch(() => hit);
      return hit || network;
    })
  );
});
