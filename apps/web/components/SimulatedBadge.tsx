export default function SimulatedBadge() {
  return (
    <div
      title="No public real-time outage feed exists for Ukraine. Road network and most facility locations are real OpenStreetMap data; power/road-blockage state shown here is a simulation for demo purposes."
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "4px 10px",
        borderRadius: 999,
        background: "#7c2d12",
        color: "#fed7aa",
        fontSize: 12,
        fontWeight: 600,
        letterSpacing: 0.3,
        cursor: "help",
      }}
    >
      ⚠ SIMULATED LIVE DATA
    </div>
  );
}
