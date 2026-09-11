import type { Metadata, Viewport } from "next";

export const metadata: Metadata = {
  title: "UkraineGrid — Resilient Resource Routing",
  description:
    "Find the nearest reachable shelter, hospital, or charging/heating point during a power outage - graph-based routing that avoids blocked roads and unpowered facilities.",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: "/icons/icon-32.png",
    apple: "/icons/icon-192.png",
  },
};

export const viewport: Viewport = {
  themeColor: "#0f172a",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, background: "#0f172a", color: "#e2e8f0", fontFamily: "system-ui, sans-serif" }}>
        {children}
      </body>
    </html>
  );
}
