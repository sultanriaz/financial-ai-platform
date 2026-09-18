import { Fragment, useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type Stats = {
  now: string;
  news_total: number;
  analysis_total: number;
  price_total: number;
  news_1m: number;
  news_5m: number;
  news_1h: number;
  sources: number;
  tickers: number;
  latest_news: string | null;
  ws_clients: number;
  histogram: { minute: string; count: number }[];
};

type Status = "ok" | "idle" | "stalled";

type NodeSpec = {
  key: string;
  label: string;
  status: Status;
  value: string;
  unit: string;
  sub: string;
};

function fmtAgo(iso: string | null): string {
  if (!iso) return "never";
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 5_000)     return "just now";
  if (diff < 60_000)    return `${Math.floor(diff / 1000)}s ago`;
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  return `${Math.floor(diff / 3_600_000)}h ago`;
}

function ActivityHistogram({ data }: { data: { minute: string; count: number }[] }) {
  const buckets = useMemo(() => {
    const now = new Date();
    now.setSeconds(0, 0);
    now.setMilliseconds(0);
    const byMinute = new Map(data.map((d) => [d.minute.slice(0, 16), d.count]));
    const out: number[] = [];
    for (let i = 59; i >= 0; i--) {
      const t = new Date(now.getTime() - i * 60_000);
      const key = t.toISOString().slice(0, 16);
      out.push(byMinute.get(key) ?? 0);
    }
    return out;
  }, [data]);

  const max = Math.max(1, ...buckets);

  return (
    <div className="pipeline-histogram">
      <div className="ph-bars">
        {buckets.map((c, i) => (
          <div
            key={i}
            className={`ph-bar${c > 0 ? " ph-bar--active" : ""}`}
            style={{ height: `${Math.max(2, (c / max) * 100)}%` }}
            title={`${c} article${c === 1 ? "" : "s"}`}
          />
        ))}
      </div>
      <div className="ph-label">Arrivals / minute · last 60 min</div>
    </div>
  );
}

export default function PipelineGraph() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const r = await fetch(`${API_BASE}/pipeline-stats`);
        if (!r.ok) throw new Error(`HTTP ${r.status} on /pipeline-stats`);
        const data: Stats = await r.json();
        if (!cancelled) { setStats(data); setError(null); }
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    };
    poll();
    const id = setInterval(poll, 3_000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const nodes: NodeSpec[] = useMemo(() => {
    if (!stats) {
      return [
        { key: "rss",  label: "RSS Feeds",  status: "idle", value: "—", unit: "", sub: "4 sources" },
        { key: "scrp", label: "Scraper",    status: "idle", value: "—", unit: "", sub: "15s poll" },
        { key: "kfk",  label: "Kafka Raw",  status: "idle", value: "—", unit: "", sub: "topic" },
        { key: "ai",   label: "AI Engine",  status: "idle", value: "—", unit: "", sub: "FinBERT + Ollama" },
        { key: "pg",   label: "Postgres",   status: "idle", value: "—", unit: "", sub: "store" },
      ];
    }
    const recent = stats.news_5m > 0;
    const flowStatus: Status = recent ? "ok" : "idle";
    const gap = stats.news_total - stats.analysis_total;
    const aiStatus: Status = gap > 5 ? "idle" : "ok";

    return [
      {
        key: "rss", label: "RSS Feeds", status: "ok",
        value: String(stats.sources), unit: "",
        sub: stats.sources === 1 ? "source" : "sources",
      },
      {
        key: "scrp", label: "Scraper", status: flowStatus,
        value: String(stats.news_1h), unit: "/hr",
        sub: `${stats.news_1m} this minute`,
      },
      {
        key: "kfk", label: "Kafka Raw", status: flowStatus,
        value: String(stats.news_total), unit: "",
        sub: "raw topic",
      },
      {
        key: "ai", label: "AI Engine", status: aiStatus,
        value: String(stats.analysis_total), unit: "",
        sub: gap > 0 ? `${gap} queued` : "all scored",
      },
      {
        key: "pg", label: "Postgres", status: "ok",
        value: String(stats.price_total), unit: "",
        sub: "price rows",
      },
    ];
  }, [stats]);

  const headerRight = stats
    ? `${stats.news_total} events · ${stats.tickers} tickers · ${stats.ws_clients} client${stats.ws_clients === 1 ? "" : "s"}`
    : error ? "offline" : "connecting…";

  const headerClass = stats ? "panel-meta panel-meta--live"
                    : error ? "panel-meta"
                    : "panel-meta";

  return (
    <div className="pipeline-panel">
      <div className="panel-heading">
        <span>Pipeline Orchestration</span>
        <span className={headerClass}>
          <span className={`panel-meta-dot${stats ? "" : " panel-meta-dot--static"}`} aria-hidden="true" />
          {headerRight}
        </span>
      </div>

      {error && (
        <div className="pipeline-error">
          <strong>Cannot reach the API.</strong> {error}
          <br />
          Verify with: <code>curl {API_BASE}/pipeline-stats</code>
        </div>
      )}

      <div className="pipeline-chain">
        {nodes.map((n, i) => (
          <Fragment key={n.key}>
            <div className={`pipeline-node pipeline-node--${n.status}`}>
              <div className="node-head">
                <span className="node-label">{n.label}</span>
                <span className={`node-status node-status--${n.status}`} aria-hidden="true" />
              </div>
              <div className="node-value">
                {n.value}
                {n.unit && <span className="node-unit">{n.unit}</span>}
              </div>
              <div className="node-sub">{n.sub}</div>
            </div>
            {i < nodes.length - 1 && (
              <div className={`pipeline-arrow pipeline-arrow--${n.status}`} aria-hidden="true" />
            )}
          </Fragment>
        ))}
      </div>

      {stats && <ActivityHistogram data={stats.histogram} />}

      {stats && (
        <div className="pipeline-footer">
          Last article: {fmtAgo(stats.latest_news)}
        </div>
      )}
    </div>
  );
}