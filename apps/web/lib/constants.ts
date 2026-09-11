// Matches scripts/build_osm_extract.py's BBOX for central Kyiv.
export const KYIV_BBOX: [number, number, number, number] = [30.495, 50.43, 30.55, 50.468];
export const KYIV_CENTER: [number, number] = [30.5225, 50.449];

export const MAP_STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";

export const FACILITY_COLORS: Record<string, string> = {
  powered: "#22c55e",
  unpowered: "#ef4444",
};

export const FACILITY_TYPE_LABELS: Record<string, string> = {
  shelter: "Shelter",
  hospital: "Hospital",
  charging_heating: "Charging / Heating Point",
};
