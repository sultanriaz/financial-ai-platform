import { useCallback, useEffect, useRef, useState } from "react";
import Analytics       from "./components/Analytics";
import ConnectionBadge from "./components/ConnectionBadge";
import LiveTicker      from "./components/LiveTicker";
import NewsStream      from "./components/NewsStream";
import PipelineGraph   from "./components/PipelineGraph";
import PricePanel      from "./components/PricePanel";
import StatusBar       from "./components/StatusBar";
import { useWebSocket } from "./hooks/useWebSocket";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8001";
const WS_URL   = import.meta.env.VITE_WS_URL       ?? "ws://localhost:8001/ws/news-stream";

const NEW_WINDOW_MS = 8_000;

export type NewsItem = {
  id:         string;
  title:      string;
  source:     string;
  url?:       string;
  timestamp?: string;
  company?:   string;
  ticker?:    string;
  score?:     number;
  sentiment?: string;
  category?:  string;
  sector?:    string;
};

export default function App() {
  const [news, setNews]           = useState<NewsItem[]>([]);
  const [newIds, setNewIds]       = useState<Set<string>>(new Set());
  const [activeTicker, setTicker] = useState<string | null>(null);
  const timers                    = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    fetch(`${API_BASE}/news?limit=50`)
      .then((r) => r.json())
      .then((items: NewsItem[]) => setNews(items))
      .catch(console.error);
  }, []);

  // Close the price panel on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setTicker(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const markNew = useCallback((id: string) => {
    setNewIds((prev) => new Set(prev).add(id));
    const existing = timers.current.get(id);
    if (existing) window.clearTimeout(existing);
    const t = window.setTimeout(() => {
      setNewIds((prev) => { const n = new Set(prev); n.delete(id); return n; });
      timers.current.delete(id);
    }, NEW_WINDOW_MS);
    timers.current.set(id, t);
  }, []);

  const handleMessage = useCallback((data: unknown) => {
    const item = data as NewsItem;
    if (!item?.id) return;
    setNews((current) => {
      if (current.some((n) => n.id === item.id)) return current;
      return [item, ...current].slice(0, 150);
    });
    markNew(item.id);
  }, [markNew]);

  const { status } = useWebSocket(WS_URL, { onMessage: handleMessage });

  return (
    <main className={`app-shell${activeTicker ? " app-shell--with-drawer" : ""}`}>
      <StatusBar apiBase={API_BASE} news={news} />
      <LiveTicker news={news} />
      <div className="meta-row">
        <ConnectionBadge status={status} />
        <span className="meta-hint">
          {news.length} events tracked · window {NEW_WINDOW_MS / 1000}s
        </span>
      </div>
      <div className="dashboard-grid">
        <PipelineGraph />
        <Analytics news={news} />
        <NewsStream news={news} newIds={newIds} onSelectTicker={setTicker} />
      </div>

      {activeTicker && (
        <PricePanel ticker={activeTicker} onClose={() => setTicker(null)} />
      )}
    </main>
  );
}