const withPWA = require("@ducanh2912/next-pwa").default({
  dest: "public",
  cacheOnFrontEndNav: true,
  aggressiveFrontEndNavCaching: true,
  reloadOnOnline: true,
  disable: process.env.NODE_ENV === "development",
  workboxOptions: {
    disableDevLogs: true,
    // Precache the app shell + icons; runtime rules for API/tiles live in
    // public/sw-runtime.js concerns are expressed here instead since
    // next-pwa/Workbox config is declarative.
    runtimeCaching: [
      {
        // Facility/road-network reads: fine to serve slightly stale while
        // refetching - offline mode falls back to this cache.
        urlPattern: ({ url }) =>
          url.pathname.startsWith("/api/facilities") || url.pathname.startsWith("/api/road-network"),
        handler: "StaleWhileRevalidate",
        options: { cacheName: "ukrainegrid-api-reads", expiration: { maxEntries: 20, maxAgeSeconds: 3600 } },
      },
      {
        // Map tiles: bounded bbox means a small, finite tile set.
        urlPattern: ({ url }) => url.hostname.includes("openfreemap.org") || url.hostname.includes("maptiler.com"),
        handler: "CacheFirst",
        options: { cacheName: "ukrainegrid-tiles", expiration: { maxEntries: 500, maxAgeSeconds: 30 * 24 * 3600 } },
      },
      {
        // Routing must always be live: stale block/power state could send
        // someone toward an unsafe route. Never cache it.
        urlPattern: ({ url }) => url.pathname.startsWith("/api/route"),
        handler: "NetworkOnly",
      },
    ],
  },
});

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
};

module.exports = withPWA(nextConfig);
