// Kira 서비스워커 — 네트워크 우선(업데이트 자동 반영) + 오프라인 캐시 대비
// 앱을 삭제하지 않아도 재실행 때마다 최신 버전을 받아온다 → localStorage(사용자 설정) 보존
const CACHE = "kira-v1";

self.addEventListener("install", (e) => {
  self.skipWaiting();
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
  if (req.method !== "GET") return;
  // 네트워크 우선: 항상 최신을 받고, 성공 시 캐시에 저장. 실패(오프라인)면 캐시 사용.
  e.respondWith(
    fetch(req)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      })
      .catch(() => caches.match(req))
  );
});
