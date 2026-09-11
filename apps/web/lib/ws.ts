"use client";

import { useEffect, useRef } from "react";
import { WS_BASE } from "./api";
import { useGridStore } from "./store";
import type { WSMessage } from "./types";

const PING_INTERVAL_MS = 15000;
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 15000;

/**
 * Frontend's live-update contract with the backend. Connects to
 * /ws/outages, applies the initial snapshot then incremental outage_update
 * diffs to the store, and reconnects with backoff on drop. Every message the
 * server sends carries simulated: true - this hook doesn't strip or hide
 * that; components read it straight from the store/UI labeling.
 */
export function useOutageSocket() {
  const applySnapshot = useGridStore((s) => s.applySnapshot);
  const applyOutageChanges = useGridStore((s) => s.applyOutageChanges);
  const setConnectionStatus = useGridStore((s) => s.setConnectionStatus);

  const attemptRef = useRef(0);
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const closedByEffectRef = useRef(false);

  useEffect(() => {
    closedByEffectRef.current = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      setConnectionStatus("connecting");
      socket = new WebSocket(`${WS_BASE}/ws/outages`);

      socket.onopen = () => {
        attemptRef.current = 0;
        setConnectionStatus("connected");
        pingTimerRef.current = setInterval(() => {
          socket?.readyState === WebSocket.OPEN && socket.send("ping");
        }, PING_INTERVAL_MS);
      };

      socket.onmessage = (event) => {
        try {
          const msg: WSMessage = JSON.parse(event.data);
          if (msg.type === "snapshot") {
            applySnapshot(msg.facilities, msg.blocked_edges.map((e) => e.id));
          } else if (msg.type === "outage_update") {
            applyOutageChanges(msg.changes);
          }
        } catch {
          // ignore malformed frames
        }
      };

      socket.onclose = () => {
        setConnectionStatus("disconnected");
        if (pingTimerRef.current) clearInterval(pingTimerRef.current);
        if (closedByEffectRef.current) return;
        const delay = Math.min(RECONNECT_BASE_MS * 2 ** attemptRef.current, RECONNECT_MAX_MS);
        attemptRef.current += 1;
        reconnectTimer = setTimeout(connect, delay);
      };

      socket.onerror = () => {
        socket?.close();
      };
    }

    connect();

    return () => {
      closedByEffectRef.current = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (pingTimerRef.current) clearInterval(pingTimerRef.current);
      socket?.close();
    };
  }, [applySnapshot, applyOutageChanges, setConnectionStatus]);
}
