"use client";

import { useGridStore } from "../lib/store";
import { FACILITY_TYPE_LABELS } from "../lib/constants";

export default function RoutePanel() {
  const origin = useGridStore((s) => s.origin);
  const route = useGridStore((s) => s.route);
  const routeError = useGridStore((s) => s.routeError);
  const routeStale = useGridStore((s) => s.routeStale);
  const isOffline = useGridStore((s) => s.isOffline);
  const requestRecompute = useGridStore((s) => s.requestRecompute);

  if (!origin) {
    return (
      <p style={{ fontSize: 13, color: "#94a3b8", margin: 0 }}>
        Click anywhere on the map to set your location, then we&apos;ll find the nearest reachable
        resource - powered and not cut off by a simulated road blockage.
      </p>
    );
  }

  if (routeError) {
    return <p style={{ fontSize: 13, color: "#fca5a5", margin: 0 }}>{routeError}</p>;
  }

  if (!route) {
    return <p style={{ fontSize: 13, color: "#94a3b8", margin: 0 }}>Computing route…</p>;
  }

  const km = (route.distance_m / 1000).toFixed(1);
  const minutes = Math.round(route.eta_seconds / 60);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: "#f1f5f9" }}>{route.facility.name}</div>
      <div style={{ fontSize: 12, color: "#94a3b8" }}>
        {FACILITY_TYPE_LABELS[route.facility.type]} · {km} km · ~{minutes} min
      </div>
      <div style={{ fontSize: 11, color: "#64748b" }}>
        Considered {route.candidates_considered} candidate{route.candidates_considered === 1 ? "" : "s"}
        {route.unreachable_candidate_ids.length > 0 &&
          ` (${route.unreachable_candidate_ids.length} unreachable, skipped)`}
      </div>

      {routeStale && !isOffline && (
        <button
          onClick={requestRecompute}
          style={{
            marginTop: 4,
            padding: "6px 10px",
            borderRadius: 8,
            border: "1px solid #b45309",
            background: "#78350f",
            color: "#fed7aa",
            fontSize: 12,
            cursor: "pointer",
          }}
        >
          ⚠ New outage reported nearby - route may no longer be valid. Recompute?
        </button>
      )}
    </div>
  );
}
