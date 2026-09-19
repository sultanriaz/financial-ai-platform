import { useEffect, useMemo, useState } from "react";
import type { NewsItem } from "../App";
import { getSentimentBucket } from "../utils/sentiment";

interface GpuInfo { available: boolean; memory_used_gb: number | null; memory_total_gb: number | null; }
interface SystemStatus {
  api: string; kafka: string; database: string;
  active_workers: number; gpu: GpuInfo; articles_per_minute: number;
}

export default function StatusBar({ apiBase, news }: { apiBase: string; news: NewsItem[] }) {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await fetch(`${apiBase}/system-status`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        if (!cancelled) { setStatus(await res.json()); setFailed(false); }
      } catch { if (!cancelled) setFailed(true); }
    };
    poll();
    const id = setInterval(poll, 5_000);
    return () => { cancelled = true; clearInterval(id); };
  }, [apiBase]);

  const { total, bullish, bearish, avg } = useMemo(() => {
    const scored = news.filter((n) => typeof n.score === "number");
    const bull   = scored.filter((n) => getSentimentBucket(n.score) === "bullish").length;
    const bear   = scored.filter((n) => getSentimentBucket(n.score) === "bearish").length;
    const mean   = scored.length ? scored.reduce((a, b) => a + (b.score ?? 0), 0) / scored.length : 0;
    return { total: news.length, bullish: bull, bearish: bear, avg: mean };
  }, [news]);

  const online  = !failed && status?.api === "online";
  const bullPct = total ? Math.round((bullish / total) * 100) : 0;
  const bearPct = total ? Math.round((bearish / total) * 100) : 0;
  const avgClass = getSentimentBucket(avg);

  return (
    <header className="status-bar" role="banner">
      <div className="brand-block">
        <div className="brand">AI NEWS ENGINE</div>
        <div className="subtitle">
          <span className={`live-dot ${online ? "live-dot--on" : "live-dot--off"}`} aria-hidden="true" />
          {online ? "STREAMING" : "OFFLINE"}
        </div>
      </div>

      <div className="kpi-strip">
        <div className="kpi">
          <div className="kpi-label">Events</div>
          <div className="kpi-value">{total}</div>
          <div className="kpi-sub">{status ? `${status.articles_per_minute}/min` : "…"}</div>
        </div>
        <div className="kpi kpi--bullish">
          <div className="kpi-label">Bullish</div>
          <div className="kpi-value">{bullPct}<span className="kpi-unit">%</span></div>
          <div className="kpi-sub">{bullish} items</div>
        </div>
        <div className="kpi kpi--bearish">
          <div className="kpi-label">Bearish</div>
          <div className="kpi-value">{bearPct}<span className="kpi-unit">%</span></div>
          <div className="kpi-sub">{bearish} items</div>
        </div>
        <div className={`kpi kpi--${avgClass}`}>
          <div className="kpi-label">Avg sentiment</div>
          <div className="kpi-value">{avg >= 0 ? "+" : ""}{avg.toFixed(2)}</div>
          <div className="kpi-sub">{status?.gpu?.available ? "GPU" : "CPU"}</div>
        </div>
      </div>
    </header>
  );
}