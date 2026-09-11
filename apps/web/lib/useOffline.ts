"use client";

import { useEffect } from "react";
import { useGridStore } from "./store";

export function useOffline() {
  const setOffline = useGridStore((s) => s.setOffline);

  useEffect(() => {
    setOffline(!navigator.onLine);
    const onOnline = () => setOffline(false);
    const onOffline = () => setOffline(true);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, [setOffline]);
}
