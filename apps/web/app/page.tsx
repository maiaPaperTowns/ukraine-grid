"use client";

import dynamic from "next/dynamic";
import ConnectionStatus from "../components/ConnectionStatus";
import FacilityTypeFilter from "../components/FacilityTypeFilter";
import OfflineBanner from "../components/OfflineBanner";
import RoutePanel from "../components/RoutePanel";
import SimulatedBadge from "../components/SimulatedBadge";
import { useOffline } from "../lib/useOffline";
import { useOutageSocket } from "../lib/ws";

// maplibre-gl touches `window` at import time - keep it out of the server bundle.
const MapView = dynamic(() => import("../components/MapView"), { ssr: false });

export default function Page() {
  useOutageSocket();
  useOffline();

  return (
    <main style={{ position: "relative", width: "100vw", height: "100dvh", overflow: "hidden" }}>
      <MapView />
      <OfflineBanner />

      <div
        style={{
          position: "absolute",
          top: 16,
          left: 16,
          zIndex: 10,
          display: "flex",
          flexDirection: "column",
          gap: 10,
          maxWidth: 340,
        }}
      >
        <div
          style={{
            background: "rgba(15, 23, 42, 0.92)",
            border: "1px solid #334155",
            borderRadius: 12,
            padding: 14,
            display: "flex",
            flexDirection: "column",
            gap: 10,
            boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
            <span style={{ fontWeight: 800, color: "#f1f5f9", fontSize: 16 }}>UkraineGrid</span>
            <ConnectionStatus />
          </div>
          <SimulatedBadge />
          <FacilityTypeFilter />
        </div>

        <div
          style={{
            background: "rgba(15, 23, 42, 0.92)",
            border: "1px solid #334155",
            borderRadius: 12,
            padding: 14,
            boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
          }}
        >
          <RoutePanel />
        </div>
      </div>
    </main>
  );
}
