import type { FacilityType, GeoJSONFeatureCollection, RouteResult } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
export const WS_BASE = process.env.NEXT_PUBLIC_WS_BASE_URL || "ws://localhost:8000";

export class RouteNotFoundError extends Error {}

export async function fetchFacilities(): Promise<GeoJSONFeatureCollection> {
  const res = await fetch(`${API_BASE}/api/facilities`);
  if (!res.ok) throw new Error(`fetchFacilities failed: ${res.status}`);
  return res.json();
}

export async function fetchRoadNetwork(): Promise<GeoJSONFeatureCollection> {
  const res = await fetch(`${API_BASE}/api/road-network`);
  if (!res.ok) throw new Error(`fetchRoadNetwork failed: ${res.status}`);
  return res.json();
}

export async function computeRoute(
  origin: { lat: number; lon: number },
  facilityType: FacilityType | null
): Promise<RouteResult> {
  const res = await fetch(`${API_BASE}/api/route`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ origin, facility_type: facilityType }),
  });
  if (res.status === 404) {
    throw new RouteNotFoundError("No reachable powered facility found.");
  }
  if (!res.ok) throw new Error(`computeRoute failed: ${res.status}`);
  return res.json();
}

export interface Stats {
  road_edges_total: number;
  road_edges_blocked: number;
  facilities_total: number;
  facilities_unpowered: number;
  last_update: string | null;
  simulated: boolean;
}

export async function fetchStats(): Promise<Stats> {
  const res = await fetch(`${API_BASE}/api/stats`);
  if (!res.ok) throw new Error(`fetchStats failed: ${res.status}`);
  return res.json();
}
