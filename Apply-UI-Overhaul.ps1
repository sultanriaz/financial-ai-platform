#Requires -Version 5.1
<#
.SYNOPSIS
    Apply the UI overhaul to Financial AI Platform.

.DESCRIPTION
    Rewrites six frontend files to add:
      - Live scrolling ticker of headlines
      - Gradient KPI strip (Events / Bullish / Bearish / Avg sentiment)
      - Arrival animations + "NEW" badge on incoming WebSocket items
      - Sentiment rail + score bar per card
      - Refined dark theme with gradient brand, grid overlay, spring motion

.USAGE
    cd C:\black_paper\Projects\financial-ai-platform
    .\Apply-UI-Overhaul.ps1

    Flags:
        -WhatIf     Preview changes without writing.
        -NoBackup   Skip .bak copies (default: create .bak once).

.NOTES
    Uses single-quoted here-strings to avoid $ interpolation issues.
    Writes UTF-8 without BOM via .NET so TypeScript/Vite are happy.
    Vite HMR picks up changes automatically — just refresh the browser.
#>
param(
    [string]$ProjectRoot = $PSScriptRoot,
    [switch]$WhatIf,
    [switch]$NoBackup
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path $ProjectRoot).Path
if (-not (Test-Path (Join-Path $ProjectRoot "frontend"))) {
    Write-Error "frontend/ not found under $ProjectRoot. Run from the project root."
    exit 1
}

function Write-TextFile {
    param(
        [string]$RelPath,
        [string]$Content
    )
    $full = Join-Path $ProjectRoot $RelPath
    $dir  = Split-Path $full -Parent

    if ($WhatIf) {
        $state = if (Test-Path $full) { "WOULD PATCH " } else { "WOULD CREATE" }
        Write-Host ("  [{0}]  {1}" -f $state, $RelPath) -ForegroundColor Yellow
        return
    }

    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    if ((Test-Path $full) -and (-not $NoBackup)) {
        $bak = "$full.bak"
        if (-not (Test-Path $bak)) { Copy-Item $full $bak }
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($full, $Content, $utf8NoBom)
    Write-Host ("  [WROTE]       {0}" -f $RelPath) -ForegroundColor Green
}

Write-Host ""
Write-Host "  Financial AI Platform - UI Overhaul" -ForegroundColor Cyan
Write-Host ("  Project root: {0}" -f $ProjectRoot)
Write-Host ("  Mode:         {0}" -f $(if ($WhatIf) { "DRY RUN" } else { "WRITE" }))
Write-Host ""

# ════════════════════════════════════════════════════════════════════════════
# 1. frontend/src/components/LiveTicker.tsx  (NEW)
# ════════════════════════════════════════════════════════════════════════════
$liveTicker = @'
import type { NewsItem } from "../App";
import { formatScore, getSentimentBucket } from "../utils/sentiment";

export default function LiveTicker({ news }: { news: NewsItem[] }) {
  const items = news.slice(0, 12);
  if (items.length === 0) {
    return (
      <div className="ticker ticker--empty">
        <span className="ticker-label">LIVE</span>
        <span className="ticker-placeholder">Awaiting first article…</span>
      </div>
    );
  }
  const doubled = [...items, ...items];
  return (
    <div className="ticker" role="marquee" aria-label="Latest headlines">
      <span className="ticker-label">LIVE</span>
      <div className="ticker-viewport">
        <div className="ticker-track">
          {doubled.map((item, i) => {
            const bucket = getSentimentBucket(item.score);
            return (
              <span key={`${item.id}-${i}`} className={`ticker-item ticker-item--${bucket}`}>
                <span className="ticker-source">{item.source}</span>
                <span className="ticker-title">{item.title}</span>
                <span className={`ticker-score score--${bucket}`}>{formatScore(item.score)}</span>
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
'@
Write-TextFile "frontend/src/components/LiveTicker.tsx" $liveTicker

# ════════════════════════════════════════════════════════════════════════════
# 2. frontend/src/App.tsx  (rewrite)
# ════════════════════════════════════════════════════════════════════════════
$appTsx = @'
import { useCallback, useEffect, useRef, useState } from "react";
import Analytics       from "./components/Analytics";
import ConnectionBadge from "./components/ConnectionBadge";
import LiveTicker      from "./components/LiveTicker";
import NewsStream      from "./components/NewsStream";
import PipelineGraph   from "./components/PipelineGraph";
import StatusBar       from "./components/StatusBar";
import { useWebSocket } from "./hooks/useWebSocket";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const WS_URL   = import.meta.env.VITE_WS_URL       ?? "ws://localhost:8000/ws/news-stream";

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
  const [news, setNews]     = useState<NewsItem[]>([]);
  const [newIds, setNewIds] = useState<Set<string>>(new Set());
  const timers              = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    fetch(`${API_BASE}/news?limit=50`)
      .then((r) => r.json())
      .then((items: NewsItem[]) => setNews(items))
      .catch(console.error);
  }, []);

  const markNew = useCallback((id: string) => {
    setNewIds((prev) => new Set(prev).add(id));
    const existing = timers.current.get(id);
    if (existing) window.clearTimeout(existing);
    const t = window.setTimeout(() => {
      setNewIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
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
    <main className="app-shell">
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
        <NewsStream news={news} newIds={newIds} />
      </div>
    </main>
  );
}
'@
Write-TextFile "frontend/src/App.tsx" $appTsx

# ════════════════════════════════════════════════════════════════════════════
# 3. frontend/src/components/NewsStream.tsx  (rewrite)
# ════════════════════════════════════════════════════════════════════════════
$newsStream = @'
import { AnimatePresence, motion } from "framer-motion";
import { useMemo, useState } from "react";
import type { NewsItem } from "../App";
import {
  formatRelativeTime,
  formatScore,
  getSentimentBucket,
  type SentimentBucket,
} from "../utils/sentiment";

const ICONS:  Record<SentimentBucket, string> = { bullish: "▲", neutral: "◆", bearish: "▼" };
const LABELS: Record<SentimentBucket, string> = { bullish: "Bullish", neutral: "Neutral", bearish: "Bearish" };

function ScoreBar({ score, bucket }: { score?: number; bucket: SentimentBucket }) {
  const pct = Math.min(100, Math.round(Math.abs(score ?? 0) * 100));
  return (
    <div className={`score-bar score-bar--${bucket}`} aria-hidden="true">
      <div className="score-bar-fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

function NewsCard({ item, isNew }: { item: NewsItem; isNew: boolean }) {
  const bucket = getSentimentBucket(item.score);
  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: -12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0,   scale: 1 }}
      exit={{ opacity: 0, x: -24, transition: { duration: 0.15 } }}
      transition={{ type: "spring", stiffness: 340, damping: 30 }}
      className={`news-card news-card--${bucket}${isNew ? " is-new" : ""}`}
      role="article"
      aria-label={`${LABELS[bucket]}: ${item.title}`}
    >
      <div className={`sentiment-rail sentiment-rail--${bucket}`} aria-hidden="true" />

      <div className="news-body">
        <header className="news-header">
          <span className="source-pill">{item.source}</span>
          {isNew && (
            <span className="new-badge">
              <span className="new-dot" aria-hidden="true" /> NEW
            </span>
          )}
          <span className="news-time">{formatRelativeTime(item.timestamp)}</span>
        </header>

        <h3 className="news-title">
          {item.url
            ? <a href={item.url} target="_blank" rel="noopener noreferrer">{item.title}</a>
            : item.title}
        </h3>

        <footer className="news-footer">
          <span className="entity">
            {item.company ?? "Unknown entity"}
            {item.ticker && <span className="ticker-tag">{item.ticker}</span>}
          </span>
          <span className={`score-display score--${bucket}`}>
            <span className="score-icon" aria-hidden="true">{ICONS[bucket]}</span>
            {formatScore(item.score)}
          </span>
        </footer>
        <ScoreBar score={item.score} bucket={bucket} />
      </div>
    </motion.article>
  );
}

export default function NewsStream({ news, newIds }: { news: NewsItem[]; newIds: Set<string> }) {
  const [sentimentFilter, setSentimentFilter] = useState<SentimentBucket | "all">("all");
  const [sourceFilter,    setSourceFilter]    = useState("");

  const sources = useMemo(
    () => Array.from(new Set(news.map((n) => n.source))).sort(),
    [news],
  );

  const filtered = useMemo(
    () => news.filter((item) => {
      if (sentimentFilter !== "all" && getSentimentBucket(item.score) !== sentimentFilter) return false;
      if (sourceFilter && item.source !== sourceFilter) return false;
      return true;
    }),
    [news, sentimentFilter, sourceFilter],
  );

  return (
    <section className="panel news-panel" aria-label="Live intelligence feed">
      <div className="panel-heading">
        <span>LIVE FEED</span>
        <span className="muted">{filtered.length} events</span>
      </div>

      <div className="news-filters" role="group" aria-label="Filter articles">
        <div className="filter-row">
          {(["all", "bullish", "neutral", "bearish"] as const).map((b) => (
            <button
              key={b}
              className={`filter-btn filter-btn--${b}${sentimentFilter === b ? " active" : ""}`}
              onClick={() => setSentimentFilter(b)}
              aria-pressed={sentimentFilter === b}
            >
              {b === "all" ? "All" : LABELS[b]}
            </button>
          ))}
        </div>
        {sources.length > 1 && (
          <select
            className="source-select"
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            aria-label="Filter by source"
          >
            <option value="">All sources</option>
            {sources.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        )}
      </div>

      <div className="news-list custom-scroll" aria-live="polite" aria-relevant="additions">
        {filtered.length === 0 ? (
          <div className="news-empty" role="status">
            {news.length === 0
              ? "Waiting for the first article…"
              : "No articles match the current filters."}
          </div>
        ) : (
          <AnimatePresence initial={false} mode="popLayout">
            {filtered.map((item) => (
              <NewsCard key={item.id} item={item} isNew={newIds.has(item.id)} />
            ))}
          </AnimatePresence>
        )}
      </div>
    </section>
  );
}
'@
Write-TextFile "frontend/src/components/NewsStream.tsx" $newsStream

# ════════════════════════════════════════════════════════════════════════════
# 4. frontend/src/components/StatusBar.tsx  (rewrite)
# ════════════════════════════════════════════════════════════════════════════
$statusBar = @'
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
  const avgClass = avg > 0.15 ? "bullish" : avg < -0.15 ? "bearish" : "neutral";

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
'@
Write-TextFile "frontend/src/components/StatusBar.tsx" $statusBar

# ════════════════════════════════════════════════════════════════════════════
# 5. frontend/src/components/Analytics.tsx  (color tokens updated)
# ════════════════════════════════════════════════════════════════════════════
$analytics = @'
import {
  Area, AreaChart, Bar, BarChart, Cell,
  Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { useMemo } from "react";
import type { NewsItem } from "../App";
import { getSentimentBucket } from "../utils/sentiment";

const COLORS = { bullish: "#34d399", neutral: "#64748b", bearish: "#f43f5e" } as const;
const TOOLTIP_STYLE = {
  background: "#0a0d14",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 10,
  fontSize: 12,
};

function buildTimeSeries(news: NewsItem[]) {
  const map = new Map<string, { time: string; bullish: number; neutral: number; bearish: number }>();
  for (const item of news) {
    if (!item.timestamp) continue;
    const d   = new Date(item.timestamp);
    const key = `${d.getHours().toString().padStart(2, "0")}:00`;
    if (!map.has(key)) map.set(key, { time: key, bullish: 0, neutral: 0, bearish: 0 });
    map.get(key)![getSentimentBucket(item.score)]++;
  }
  return Array.from(map.values())
    .sort((a, b) => a.time.localeCompare(b.time))
    .slice(-12);
}

export default function Analytics({ news }: { news: NewsItem[] }) {
  const distribution = useMemo(() => [
    { name: "Bullish", count: news.filter((i) => getSentimentBucket(i.score) === "bullish").length },
    { name: "Neutral", count: news.filter((i) => getSentimentBucket(i.score) === "neutral").length },
    { name: "Bearish", count: news.filter((i) => getSentimentBucket(i.score) === "bearish").length },
  ], [news]);

  const timeSeries = useMemo(() => buildTimeSeries(news), [news]);

  return (
    <div className="analytics-wrapper">
      <section className="panel analytics-panel" aria-label="Sentiment distribution">
        <div className="panel-heading">SENTIMENT DISTRIBUTION</div>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={distribution} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
            <XAxis dataKey="name" stroke="#55627a" tick={{ fontSize: 11 }} />
            <YAxis stroke="#55627a" tick={{ fontSize: 11 }} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Bar dataKey="count" radius={[5, 5, 0, 0]}>
              {distribution.map((entry) => (
                <Cell key={entry.name} fill={COLORS[entry.name.toLowerCase() as keyof typeof COLORS]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </section>

      {timeSeries.length > 1 && (
        <section className="panel analytics-panel" aria-label="Sentiment over time">
          <div className="panel-heading">SENTIMENT TIMELINE</div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={timeSeries} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <XAxis dataKey="time" stroke="#55627a" tick={{ fontSize: 10 }} />
              <YAxis stroke="#55627a" tick={{ fontSize: 10 }} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
              <Area type="monotone" dataKey="bullish" stackId="s" stroke={COLORS.bullish} fill={COLORS.bullish} fillOpacity={0.2} />
              <Area type="monotone" dataKey="neutral"  stackId="s" stroke={COLORS.neutral}  fill={COLORS.neutral}  fillOpacity={0.2} />
              <Area type="monotone" dataKey="bearish"  stackId="s" stroke={COLORS.bearish}  fill={COLORS.bearish}  fillOpacity={0.2} />
            </AreaChart>
          </ResponsiveContainer>
        </section>
      )}
    </div>
  );
}
'@
Write-TextFile "frontend/src/components/Analytics.tsx" $analytics

# ════════════════════════════════════════════════════════════════════════════
# 6. frontend/src/styles.css  (full rewrite)
# ════════════════════════════════════════════════════════════════════════════
$stylesCss = @'
/* ─── tokens ────────────────────────────────────────────────────────────────── */
:root {
  --bg:         #05060a;
  --bg-elev:    #0a0d14;
  --surface:    rgba(255,255,255,0.028);
  --surface-2:  rgba(255,255,255,0.05);
  --border:     rgba(255,255,255,0.07);
  --border-hi:  rgba(255,255,255,0.14);

  --text:       #e6edf7;
  --text-dim:   #8a97aa;
  --text-mute:  #55627a;

  --cyan:       #22d3ee;
  --violet:     #a855f7;
  --bullish:    #34d399;
  --bearish:    #f43f5e;
  --neutral:    #64748b;

  --radius:     18px;
  --radius-sm:  12px;
  --ease:       cubic-bezier(0.22, 1, 0.36, 1);
}

* { box-sizing: border-box; }

html, body { margin: 0; }

body {
  color: var(--text);
  font-family: "Inter", ui-sans-serif, system-ui, -apple-system, sans-serif;
  font-feature-settings: "cv11", "ss01";
  background:
    radial-gradient(1200px 600px at 12% -8%,  rgba(34,211,238,0.09), transparent 60%),
    radial-gradient(1000px 500px at 95% 8%,   rgba(168,85,247,0.08), transparent 55%),
    radial-gradient(800px 700px  at 50% 120%, rgba(34,211,238,0.05), transparent 60%),
    var(--bg);
  min-height: 100vh;
}

body::before {
  content: "";
  position: fixed; inset: 0;
  background-image:
    linear-gradient(rgba(255,255,255,0.018) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.018) 1px, transparent 1px);
  background-size: 40px 40px;
  pointer-events: none;
  z-index: 0;
  mask-image: radial-gradient(ellipse at center, black 30%, transparent 85%);
  -webkit-mask-image: radial-gradient(ellipse at center, black 30%, transparent 85%);
}

.app-shell {
  position: relative;
  z-index: 1;
  max-width: 1680px;
  margin: 0 auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* ─── status bar / KPI ──────────────────────────────────────────────────────── */
.status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 24px;
  padding: 20px 24px;
  background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01));
  border: 1px solid var(--border);
  border-radius: var(--radius);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 1px 0 rgba(255,255,255,0.05) inset, 0 20px 40px -20px rgba(0,0,0,0.6);
}

.brand-block { display: flex; flex-direction: column; gap: 6px; }

.brand {
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0.22em;
  background: linear-gradient(90deg, var(--cyan), var(--violet));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.subtitle {
  display: flex; align-items: center; gap: 8px;
  font-size: 10px;
  letter-spacing: 0.18em;
  color: var(--text-dim);
  font-weight: 600;
}

.live-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.live-dot--on  { background: var(--bullish); box-shadow: 0 0 12px var(--bullish); animation: pulse 1.8s ease-in-out infinite; }
.live-dot--off { background: var(--bearish); box-shadow: 0 0 10px var(--bearish); }

@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }

.kpi-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
  gap: 10px;
  flex: 1;
  max-width: 780px;
}

.kpi {
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  background: var(--surface);
  border: 1px solid var(--border);
  transition: border-color 0.2s, transform 0.2s var(--ease);
}
.kpi:hover { border-color: var(--border-hi); transform: translateY(-1px); }

.kpi-label {
  font-size: 9.5px;
  letter-spacing: 0.16em;
  color: var(--text-mute);
  text-transform: uppercase;
  font-weight: 700;
  margin-bottom: 6px;
}
.kpi-value {
  font-size: 26px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
}
.kpi-unit { font-size: 14px; font-weight: 600; color: var(--text-dim); margin-left: 2px; }
.kpi-sub { margin-top: 6px; font-size: 10.5px; color: var(--text-mute); letter-spacing: 0.04em; }

.kpi--bullish .kpi-value { color: var(--bullish); }
.kpi--bearish .kpi-value { color: var(--bearish); }
.kpi--neutral .kpi-value { color: var(--text); }

/* ─── ticker ────────────────────────────────────────────────────────────────── */
.ticker {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 42px;
  padding: 0 16px;
  background: linear-gradient(90deg, rgba(34,211,238,0.06), rgba(168,85,247,0.05) 70%, transparent);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}
.ticker--empty { color: var(--text-mute); font-size: 12px; }

.ticker-label {
  flex-shrink: 0;
  padding: 3px 9px;
  font-size: 9.5px;
  font-weight: 800;
  letter-spacing: 0.16em;
  color: var(--bg);
  background: linear-gradient(90deg, var(--cyan), var(--violet));
  border-radius: 4px;
}

.ticker-viewport { overflow: hidden; flex: 1; position: relative; }
.ticker-viewport::after {
  content: "";
  position: absolute; right: 0; top: 0; bottom: 0; width: 60px;
  background: linear-gradient(90deg, transparent, var(--bg));
  pointer-events: none;
}

.ticker-track {
  display: flex;
  gap: 40px;
  white-space: nowrap;
  animation: ticker-scroll 70s linear infinite;
  will-change: transform;
}
.ticker:hover .ticker-track { animation-play-state: paused; }

@keyframes ticker-scroll {
  from { transform: translateX(0); }
  to   { transform: translateX(-50%); }
}

.ticker-item { display: inline-flex; align-items: center; gap: 10px; font-size: 12.5px; color: var(--text-dim); }
.ticker-source { font-weight: 700; font-size: 10px; letter-spacing: 0.1em; color: var(--cyan); text-transform: uppercase; }
.ticker-title { color: var(--text); font-weight: 500; }
.ticker-score { font-weight: 700; font-variant-numeric: tabular-nums; }
.ticker-placeholder { font-size: 12px; letter-spacing: 0.08em; }

/* ─── meta row ──────────────────────────────────────────────────────────────── */
.meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4px;
  font-size: 11px;
  color: var(--text-mute);
  letter-spacing: 0.08em;
}
.meta-hint { letter-spacing: 0.06em; }

.connection-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 12px;
  border-radius: 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  font-size: 11px;
  font-weight: 600;
}
.pulse-dot { animation: pulse 1.8s ease-in-out infinite; }

/* ─── grid ──────────────────────────────────────────────────────────────────── */
.dashboard-grid {
  display: grid;
  grid-template-columns: 1.55fr 0.9fr;
  gap: 14px;
}

@media (max-width: 1200px) { .dashboard-grid { grid-template-columns: 1fr; } }

.panel {
  background: linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.008));
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px;
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  box-shadow: 0 1px 0 rgba(255,255,255,0.04) inset, 0 20px 40px -24px rgba(0,0,0,0.5);
  transition: border-color 0.25s, box-shadow 0.25s;
}
.panel:hover {
  border-color: var(--border-hi);
  box-shadow: 0 1px 0 rgba(255,255,255,0.06) inset, 0 24px 48px -20px rgba(0,0,0,0.6);
}

.pipeline-panel { grid-column: 1 / -1; padding: 18px; overflow: hidden; }
.pipeline-canvas { height: 300px; margin-top: 4px; }

.panel-heading {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 10.5px;
  font-weight: 800;
  letter-spacing: 0.2em;
  color: var(--text-dim);
  padding-bottom: 14px;
  margin-bottom: 4px;
  border-bottom: 1px solid var(--border);
}
.muted { color: var(--text-mute); font-weight: 600; letter-spacing: 0.08em; font-size: 10px; }

/* ─── news panel ────────────────────────────────────────────────────────────── */
.news-panel { display: flex; flex-direction: column; min-height: 640px; max-height: 820px; }
.analytics-wrapper { display: flex; flex-direction: column; gap: 14px; }

.news-filters {
  display: flex; flex-wrap: wrap; gap: 8px;
  margin: 14px 0 12px;
  align-items: center;
}
.filter-row { display: flex; gap: 6px; flex-wrap: wrap; }

.filter-btn {
  padding: 5px 13px;
  border-radius: 20px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-dim);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: all 0.15s;
}
.filter-btn:hover { color: var(--text); border-color: var(--border-hi); background: var(--surface-2); }
.filter-btn.active { color: var(--cyan); border-color: rgba(34,211,238,0.5); background: rgba(34,211,238,0.09); }
.filter-btn--bullish.active { color: var(--bullish); border-color: rgba(52,211,153,0.5); background: rgba(52,211,153,0.1); }
.filter-btn--bearish.active { color: var(--bearish); border-color: rgba(244,63,94,0.5);  background: rgba(244,63,94,0.1); }

.source-select {
  margin-left: auto;
  padding: 5px 12px;
  border-radius: 20px;
  border: 1px solid var(--border);
  background: var(--bg-elev);
  color: var(--text-dim);
  font-size: 11px;
  font-weight: 600;
  outline: none;
  cursor: pointer;
}

/* ─── news list ─────────────────────────────────────────────────────────────── */
.news-list {
  display: flex; flex-direction: column; gap: 10px;
  overflow-y: auto;
  padding-right: 6px;
  flex: 1;
  min-height: 0;
}

.custom-scroll::-webkit-scrollbar       { width: 6px; }
.custom-scroll::-webkit-scrollbar-track { background: transparent; }
.custom-scroll::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
.custom-scroll::-webkit-scrollbar-thumb:hover { background: rgba(34,211,238,0.4); }
.custom-scroll { scrollbar-width: thin; scrollbar-color: rgba(255,255,255,0.1) transparent; }

.news-empty {
  padding: 60px 20px;
  text-align: center;
  color: var(--text-mute);
  font-size: 13px;
  letter-spacing: 0.02em;
  font-style: italic;
}

/* ─── news card ─────────────────────────────────────────────────────────────── */
.news-card {
  position: relative;
  display: flex;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  transition: background 0.18s, border-color 0.18s, transform 0.18s var(--ease);
}
.news-card:hover {
  background: var(--surface-2);
  border-color: var(--border-hi);
  transform: translateY(-1px);
}

@keyframes arrival {
  0% {
    background: rgba(34,211,238,0.16);
    box-shadow: 0 0 0 1px rgba(34,211,238,0.55), 0 0 40px rgba(34,211,238,0.25);
  }
  100% { background: transparent; box-shadow: none; }
}
.news-card.is-new { animation: arrival 2.6s var(--ease); }

.sentiment-rail { width: 4px; flex-shrink: 0; }
.sentiment-rail--bullish { background: var(--bullish); box-shadow: 0 0 20px var(--bullish); }
.sentiment-rail--bearish { background: var(--bearish); box-shadow: 0 0 20px var(--bearish); }
.sentiment-rail--neutral { background: var(--neutral); }

.news-body { flex: 1; padding: 14px 16px 12px; min-width: 0; }

.news-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  font-size: 10.5px;
  letter-spacing: 0.08em;
}

.source-pill {
  padding: 3px 9px;
  border-radius: 4px;
  background: rgba(34,211,238,0.1);
  color: var(--cyan);
  font-weight: 700;
  text-transform: uppercase;
  font-size: 9.5px;
  letter-spacing: 0.12em;
}

.new-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--cyan), var(--violet));
  color: #05060a;
  font-weight: 800;
  font-size: 9.5px;
  letter-spacing: 0.14em;
}
.new-dot {
  width: 5px; height: 5px; border-radius: 50%;
  background: #05060a;
  animation: pulse 1s ease-in-out infinite;
}

.news-time { margin-left: auto; color: var(--text-mute); font-weight: 500; }

.news-title {
  margin: 0 0 12px;
  font-size: 14.5px;
  font-weight: 600;
  line-height: 1.45;
  color: var(--text);
  letter-spacing: -0.005em;
}
.news-title a { color: inherit; text-decoration: none; transition: color 0.15s; }
.news-title a:hover { color: var(--cyan); }

.news-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 11px;
  color: var(--text-dim);
}

.entity { display: inline-flex; align-items: center; gap: 8px; }
.ticker-tag {
  padding: 2px 7px;
  border-radius: 4px;
  background: rgba(168,85,247,0.13);
  color: var(--violet);
  font-weight: 700;
  font-size: 9.5px;
  letter-spacing: 0.08em;
}

.score-display {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  font-size: 12px;
}
.score-icon { font-size: 9px; }

.score--bullish { color: var(--bullish); }
.score--bearish { color: var(--bearish); }
.score--neutral { color: var(--neutral); }

.score-bar {
  margin-top: 10px;
  height: 2px;
  background: rgba(255,255,255,0.04);
  border-radius: 2px;
  overflow: hidden;
}
.score-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.4s var(--ease);
}
.score-bar--bullish .score-bar-fill { background: var(--bullish); }
.score-bar--bearish .score-bar-fill { background: var(--bearish); }
.score-bar--neutral .score-bar-fill { background: var(--neutral); }

/* ─── react flow ────────────────────────────────────────────────────────────── */
.react-flow__node {
  width: 175px;
  padding: 12px 14px;
  white-space: pre-line;
  text-align: center;
  font-size: 10.5px;
  letter-spacing: 0.06em;
  font-weight: 600;
  color: var(--text);
  background: linear-gradient(145deg, rgba(34,211,238,0.08), rgba(168,85,247,0.06));
  border: 1px solid rgba(34,211,238,0.35);
  border-radius: 12px;
  box-shadow: 0 0 24px -8px rgba(34,211,238,0.4);
  transition: box-shadow 0.2s, transform 0.2s;
}
.react-flow__node:hover {
  box-shadow: 0 0 32px -4px rgba(34,211,238,0.65);
  transform: translateY(-1px);
}
.react-flow__controls {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: 8px;
}
.react-flow__controls-button {
  background: transparent;
  border-bottom-color: var(--border);
  color: var(--text-dim);
}
.react-flow__controls-button:hover { background: var(--surface-2); color: var(--text); }

/* ─── mobile ────────────────────────────────────────────────────────────────── */
@media (max-width: 720px) {
  .app-shell { padding: 12px; gap: 10px; }
  .kpi-strip { grid-template-columns: repeat(2, 1fr); max-width: none; width: 100%; }
  .status-bar { padding: 16px; }
  .kpi-value { font-size: 22px; }
  .pipeline-canvas { height: 220px; }
  .news-panel { min-height: 480px; max-height: none; }
}
'@
Write-TextFile "frontend/src/styles.css" $stylesCss

# ════════════════════════════════════════════════════════════════════════════
# Done
# ════════════════════════════════════════════════════════════════════════════
Write-Host ""
if ($WhatIf) {
    Write-Host "  DRY RUN complete — no files were written." -ForegroundColor Yellow
} else {
    Write-Host "  6 files written." -ForegroundColor Green
    Write-Host ""
    Write-Host "  Next steps:" -ForegroundColor Cyan
    Write-Host "    1. cd frontend"
    Write-Host "    2. npm run dev   (if not already running)"
    Write-Host "    3. Open http://localhost:5173"
    Write-Host ""
    Write-Host "  Vite HMR picks up .tsx/.css changes automatically — no restart needed."
    Write-Host "  To revert: copy the .bak files back over the originals." -ForegroundColor DarkGray
}
Write-Host ""