"use client";

import { FACILITY_TYPE_LABELS } from "../lib/constants";
import { useGridStore } from "../lib/store";
import type { FacilityType } from "../lib/types";

const OPTIONS: (FacilityType | null)[] = [null, "shelter", "hospital", "charging_heating"];

export default function FacilityTypeFilter() {
  const filter = useGridStore((s) => s.facilityTypeFilter);
  const setFilter = useGridStore((s) => s.setFacilityTypeFilter);

  return (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
      {OPTIONS.map((opt) => (
        <button
          key={opt ?? "any"}
          onClick={() => setFilter(opt)}
          style={{
            padding: "6px 10px",
            borderRadius: 8,
            border: "1px solid #334155",
            background: filter === opt ? "#2563eb" : "#1e293b",
            color: "#e2e8f0",
            fontSize: 12,
            cursor: "pointer",
          }}
        >
          {opt ? FACILITY_TYPE_LABELS[opt] : "Any type"}
        </button>
      ))}
    </div>
  );
}
