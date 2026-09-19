// Single source of truth for the backend base URLs. Every component should
// import from here instead of hardcoding a host/port or re-reading the env
// vars itself — that duplication is exactly what caused the frontend to
// drift out of sync with the backend port in the past.
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
export const WS_URL   = import.meta.env.VITE_WS_URL       ?? "ws://localhost:8000/ws/news-stream";
