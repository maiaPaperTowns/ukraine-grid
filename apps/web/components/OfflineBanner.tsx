"use client";

import { useGridStore } from "../lib/store";

export default function OfflineBanner() {
  const isOffline = useGridStore((s) => s.isOffline);
  const lastSyncedAt = useGridStore((s) => s.lastSyncedAt);

  if (!isOffline) return null;

  const when = lastSyncedAt ? new Date(lastSyncedAt).toLocaleTimeString() : "unknown time";

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        zIndex: 20,
        background: "#7f1d1d",
        color: "#fecaca",
        fontSize: 13,
        padding: "8px 16px",
        textAlign: "center",
      }}
    >
      OFFLINE - showing last-known state as of {when}. Finding a route requires a connection and is
      disabled until you&apos;re back online (routing on stale data could send you somewhere unsafe).
    </div>
  );
}
