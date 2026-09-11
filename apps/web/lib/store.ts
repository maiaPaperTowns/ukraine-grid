import { create } from "zustand";
import type { Facility, FacilityType, OutageChange, RouteResult } from "./types";

export type ConnectionStatus = "connecting" | "connected" | "disconnected";

interface GridState {
  facilities: Record<number, Facility>;
  blockedEdgeIds: Set<number>;
  facilityTypeFilter: FacilityType | null;
  origin: { lat: number; lon: number } | null;
  route: RouteResult | null;
  routeError: string | null;
  routeStale: boolean;
  connectionStatus: ConnectionStatus;
  lastSyncedAt: string | null;
  isOffline: boolean;
  recomputeToken: number;

  setFacilitiesFromFeatureCollection: (features: any[]) => void;
  requestRecompute: () => void;
  setFacilityTypeFilter: (t: FacilityType | null) => void;
  setOrigin: (o: { lat: number; lon: number } | null) => void;
  setRoute: (r: RouteResult | null, error?: string | null) => void;
  applySnapshot: (facilities: { id: number; power_status: Facility["power_status"] }[], blockedEdgeIds: number[]) => void;
  applyOutageChanges: (changes: OutageChange[]) => void;
  setConnectionStatus: (s: ConnectionStatus) => void;
  setOffline: (o: boolean) => void;
}

export const useGridStore = create<GridState>((set, get) => ({
  facilities: {},
  blockedEdgeIds: new Set(),
  facilityTypeFilter: null,
  origin: null,
  route: null,
  routeError: null,
  routeStale: false,
  connectionStatus: "connecting",
  lastSyncedAt: null,
  isOffline: false,
  recomputeToken: 0,

  requestRecompute: () => set((s) => ({ recomputeToken: s.recomputeToken + 1, routeStale: false })),

  setFacilitiesFromFeatureCollection: (features) => {
    const facilities: Record<number, Facility> = {};
    for (const f of features) {
      const p = f.properties;
      facilities[p.id] = { ...p, lat: f.geometry.coordinates[1], lon: f.geometry.coordinates[0] };
    }
    set({ facilities, lastSyncedAt: new Date().toISOString() });
  },

  setFacilityTypeFilter: (t) => set({ facilityTypeFilter: t }),
  setOrigin: (o) => set({ origin: o, route: null, routeError: null, routeStale: false }),

  setRoute: (r, error = null) => set({ route: r, routeError: error, routeStale: false }),

  applySnapshot: (facilities, blockedEdgeIds) => {
    set((state) => {
      const next = { ...state.facilities };
      for (const f of facilities) {
        if (next[f.id]) next[f.id] = { ...next[f.id], power_status: f.power_status };
      }
      return {
        facilities: next,
        blockedEdgeIds: new Set(blockedEdgeIds),
        lastSyncedAt: new Date().toISOString(),
      };
    });
  },

  applyOutageChanges: (changes) => {
    set((state) => {
      const next = { ...state.facilities };
      const nextBlocked = new Set(state.blockedEdgeIds);
      let touchesLiveRoute = false;

      for (const c of changes) {
        if (c.target_type === "facility" && c.field === "power_status") {
          if (next[c.id]) next[c.id] = { ...next[c.id], power_status: c.new_value as Facility["power_status"] };
          if (state.route && state.route.facility.id === c.id) touchesLiveRoute = true;
        } else if (c.target_type === "edge" && c.field === "blocked") {
          if (c.new_value) nextBlocked.add(c.id);
          else nextBlocked.delete(c.id);
          // Coarse but honest: any new edge block/unblock while a route is on
          // screen is treated as "may no longer be valid" - we don't carry
          // per-edge-id path correlation down to the frontend, so this can't
          // know for certain the route crosses this exact edge.
          if (state.route) touchesLiveRoute = true;
        }
      }

      return {
        facilities: next,
        blockedEdgeIds: nextBlocked,
        lastSyncedAt: new Date().toISOString(),
        routeStale: state.route ? state.routeStale || touchesLiveRoute : false,
      };
    });
  },

  setConnectionStatus: (s) => set({ connectionStatus: s }),
  setOffline: (o) => set({ isOffline: o }),
}));
