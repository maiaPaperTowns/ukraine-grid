"use client";

import { useGridStore } from "../lib/store";

const LABEL: Record<string, string> = {
  connecting: "Connecting…",
  connected: "Live",
  disconnected: "Reconnecting…",
};

const COLOR: Record<string, string> = {
  connecting: "#facc15",
  connected: "#22c55e",
  disconnected: "#ef4444",
};

export default function ConnectionStatus() {
  const status = useGridStore((s) => s.connectionStatus);
  const isOffline = useGridStore((s) => s.isOffline);

  const label = isOffline ? "Offline" : LABEL[status];
  const color = isOffline ? "#ef4444" : COLOR[status];

  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, color: "#cbd5e1" }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, display: "inline-block" }} />
      {label}
    </div>
  );
}
