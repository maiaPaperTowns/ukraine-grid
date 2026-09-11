"use client";

import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import { computeRoute, fetchFacilities, fetchRoadNetwork, RouteNotFoundError } from "../lib/api";
import { FACILITY_COLORS, KYIV_BBOX, KYIV_CENTER, MAP_STYLE_URL } from "../lib/constants";
import { useGridStore } from "../lib/store";

interface RoadEdgeRow {
  id: number;
  coords: [number, number][];
}

const FACILITIES_SOURCE = "facilities";
const ROADS_SOURCE = "roads";
const BLOCKED_SOURCE = "blocked-edges";
const ROUTE_SOURCE = "route";
const ORIGIN_SOURCE = "origin";

export default function MapView() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const roadEdgesRef = useRef<RoadEdgeRow[]>([]);
  const [mapReady, setMapReady] = useState(false);

  const facilities = useGridStore((s) => s.facilities);
  const blockedEdgeIds = useGridStore((s) => s.blockedEdgeIds);
  const facilityTypeFilter = useGridStore((s) => s.facilityTypeFilter);
  const origin = useGridStore((s) => s.origin);
  const route = useGridStore((s) => s.route);
  const setOrigin = useGridStore((s) => s.setOrigin);
  const setRoute = useGridStore((s) => s.setRoute);
  const recomputeToken = useGridStore((s) => s.recomputeToken);
  const setFacilitiesFromFeatureCollection = useGridStore((s) => s.setFacilitiesFromFeatureCollection);

  // --- init map + load initial data once ---
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE_URL,
      center: KYIV_CENTER,
      zoom: 13.5,
      bounds: KYIV_BBOX,
      fitBoundsOptions: { padding: 20 },
    });
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    mapRef.current = map;

    map.on("load", async () => {
      map.addSource(ROADS_SOURCE, { type: "geojson", data: emptyFC() });
      map.addLayer({
        id: ROADS_SOURCE,
        type: "line",
        source: ROADS_SOURCE,
        paint: { "line-color": "#64748b", "line-width": 1.5, "line-opacity": 0.6 },
      });

      map.addSource(BLOCKED_SOURCE, { type: "geojson", data: emptyFC() });
      map.addLayer({
        id: BLOCKED_SOURCE,
        type: "line",
        source: BLOCKED_SOURCE,
        paint: { "line-color": "#ef4444", "line-width": 3, "line-dasharray": [1.5, 1.5] },
      });

      map.addSource(ROUTE_SOURCE, { type: "geojson", data: emptyFC() });
      map.addLayer({
        id: ROUTE_SOURCE,
        type: "line",
        source: ROUTE_SOURCE,
        paint: { "line-color": "#2563eb", "line-width": 5, "line-opacity": 0.85 },
      });

      map.addSource(FACILITIES_SOURCE, { type: "geojson", data: emptyFC() });
      map.addLayer({
        id: FACILITIES_SOURCE,
        type: "circle",
        source: FACILITIES_SOURCE,
        paint: {
          "circle-radius": 7,
          "circle-color": ["match", ["get", "power_status"], "powered", FACILITY_COLORS.powered, FACILITY_COLORS.unpowered],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#0f172a",
        },
      });

      map.addSource(ORIGIN_SOURCE, { type: "geojson", data: emptyFC() });
      map.addLayer({
        id: ORIGIN_SOURCE,
        type: "circle",
        source: ORIGIN_SOURCE,
        paint: { "circle-radius": 9, "circle-color": "#facc15", "circle-stroke-width": 2, "circle-stroke-color": "#0f172a" },
      });

      map.on("click", (e) => {
        // Read fresh (not the closed-over stale value) - this handler is
        // registered once at map load. Routing needs a live API round trip,
        // so it's disabled while offline: stale block/power state could
        // silently send someone toward an unsafe route.
        if (useGridStore.getState().isOffline) return;
        setOrigin({ lat: e.lngLat.lat, lon: e.lngLat.lng });
      });

      map.on("mouseenter", FACILITIES_SOURCE, (e) => {
        map.getCanvas().style.cursor = "pointer";
        const f = e.features?.[0];
        if (!f) return;
        new maplibregl.Popup({ closeButton: false, offset: 10 })
          .setLngLat((e.lngLat as any))
          .setHTML(
            `<strong>${escapeHtml(f.properties?.name)}</strong><br/>${f.properties?.type} - ${f.properties?.power_status}`
          )
          .addTo(map);
      });
      map.on("mouseleave", FACILITIES_SOURCE, () => {
        map.getCanvas().style.cursor = "";
      });

      try {
        const [facilitiesFC, roadsFC] = await Promise.all([fetchFacilities(), fetchRoadNetwork()]);
        setFacilitiesFromFeatureCollection(facilitiesFC.features);
        roadEdgesRef.current = roadsFC.features.map((f) => ({
          id: f.properties.id,
          coords: f.geometry.coordinates,
        }));
        (map.getSource(ROADS_SOURCE) as maplibregl.GeoJSONSource).setData(roadsFC as any);
      } catch (err) {
        // Expected whenever the API is unreachable (e.g. backend not running
        // yet) - console.warn rather than .error so Next.js dev mode doesn't
        // surface this as a crash overlay for what is a normal, handled state.
        console.warn("Failed to load initial map data - is the API running?", err);
      }

      setMapReady(true);
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- facilities layer reacts to store (initial load + WS power_status changes) ---
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const list = Object.values(facilities).filter(
      (f) => !facilityTypeFilter || f.type === facilityTypeFilter
    );
    const fc = {
      type: "FeatureCollection" as const,
      features: list.map((f) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [f.lon, f.lat] },
        properties: f,
      })),
    };
    (map.getSource(FACILITIES_SOURCE) as maplibregl.GeoJSONSource)?.setData(fc as any);
  }, [facilities, facilityTypeFilter, mapReady]);

  // --- blocked-edges overlay reacts to WS updates ---
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const blocked = roadEdgesRef.current.filter((e) => blockedEdgeIds.has(e.id));
    const fc = {
      type: "FeatureCollection" as const,
      features: blocked.map((e) => ({
        type: "Feature" as const,
        geometry: { type: "LineString" as const, coordinates: e.coords },
        properties: { id: e.id },
      })),
    };
    (map.getSource(BLOCKED_SOURCE) as maplibregl.GeoJSONSource)?.setData(fc as any);
  }, [blockedEdgeIds, mapReady]);

  // --- origin marker ---
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const fc = origin
      ? {
          type: "FeatureCollection" as const,
          features: [{ type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [origin.lon, origin.lat] }, properties: {} }],
        }
      : emptyFC();
    (map.getSource(ORIGIN_SOURCE) as maplibregl.GeoJSONSource)?.setData(fc as any);
  }, [origin, mapReady]);

  // --- route line ---
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const fc = route
      ? { type: "FeatureCollection" as const, features: [{ type: "Feature" as const, geometry: route.path, properties: {} }] }
      : emptyFC();
    (map.getSource(ROUTE_SOURCE) as maplibregl.GeoJSONSource)?.setData(fc as any);
  }, [route, mapReady]);

  // --- compute route whenever origin or filter changes ---
  useEffect(() => {
    if (!origin) return;
    let cancelled = false;
    (async () => {
      try {
        const result = await computeRoute(origin, facilityTypeFilter);
        if (!cancelled) setRoute(result);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof RouteNotFoundError) {
          setRoute(null, "No reachable powered facility found from this origin.");
        } else {
          setRoute(null, "Failed to compute route - check that the API is reachable.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [origin, facilityTypeFilter, recomputeToken, setRoute]);

  return <div ref={containerRef} style={{ position: "absolute", inset: 0 }} />;
}

function emptyFC() {
  return { type: "FeatureCollection" as const, features: [] as any[] };
}

function escapeHtml(s: unknown): string {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] as string));
}
