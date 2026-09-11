export type FacilityType = "shelter" | "hospital" | "charging_heating";
export type PowerStatus = "powered" | "unpowered";

export interface Facility {
  id: number;
  osm_id: string | null;
  type: FacilityType;
  name: string;
  lat: number;
  lon: number;
  power_status: PowerStatus;
  capacity: number | null;
  is_synthetic: boolean;
}

export interface GeoJSONFeatureCollection {
  type: "FeatureCollection";
  features: any[];
  simulated: boolean;
}

export interface RouteResult {
  facility: Facility;
  path: { type: "LineString"; coordinates: [number, number][] };
  distance_m: number;
  eta_seconds: number;
  candidates_considered: number;
  unreachable_candidate_ids: number[];
  simulated: boolean;
}

export interface OutageChange {
  target_type: "edge" | "facility";
  id: number;
  field: "blocked" | "power_status";
  new_value: boolean | PowerStatus;
  reason: string | null;
  simulated: true;
}

export interface SnapshotMessage {
  type: "snapshot";
  simulated: true;
  facilities: { id: number; type: FacilityType; power_status: PowerStatus }[];
  blocked_edges: { id: number; reason: string | null }[];
}

export interface OutageUpdateMessage {
  type: "outage_update";
  simulated: true;
  timestamp: string;
  changes: OutageChange[];
}

export type WSMessage = SnapshotMessage | OutageUpdateMessage;
