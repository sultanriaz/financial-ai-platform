// FIX #8 / UI: Visible WebSocket connection indicator tied to actual socket state.
// The original app had no visual feedback if the connection dropped or was reconnecting.
import type { WsStatus } from "../hooks/useWebSocket";

const META: Record<WsStatus, { label: string; color: string; pulse: boolean }> = {
  connecting:   { label: "Connecting…",   color: "#f59e0b", pulse: false },
  connected:    { label: "Live",          color: "#46f6a6", pulse: true  },
  disconnected: { label: "Reconnecting…", color: "#f59e0b", pulse: false },
  error:        { label: "WS Error",      color: "#ff557c", pulse: false },
};

export default function ConnectionBadge({ status }: { status: WsStatus }) {
  const { label, color, pulse } = META[status];
  return (
    <div
      className="connection-badge"
      role="status"
      aria-label={`WebSocket: ${label}`}
      title={`WebSocket status: ${label}`}
    >
      <span
        className={pulse ? "pulse-dot" : undefined}
        style={{ color, textShadow: `0 0 8px ${color}` }}
        aria-hidden="true"
      >
        ●
      </span>
      <span style={{ color, fontSize: 11, letterSpacing: ".06em" }}>{label}</span>
    </div>
  );
}
