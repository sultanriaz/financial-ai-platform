import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer,
  Scatter, Tooltip, XAxis, YAxis,
} from "recharts";
import { API_BASE } from "../config";
import { getSentimentBucket } from "../utils/sentiment";

type PriceRow  = { ts: string; open: number; high: number; low: number; close: number; volume: number | null };
type EventRow  = { ts: string; score: number; sentiment: string; title: string; url: string; news_id: string };

const COLORS = { bullish: "#34d399", neutral: "#64748b", bearish: "#f43f5e" } as const;
const TOOLTIP_STYLE = {
  background: "#0a0d14",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 10,
  fontSize: 12,
  maxWidth: 360,
};

const bucketOf = getSentimentBucket;

function fmtDay(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
function fmtTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit" });
}

function EventTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const p = payload[0]?.payload;
  if (!p?.event) return null;
  const b = bucketOf(p.event.score);
  return (
    <div className="price-event-tooltip">
      <div className="pet-time">{fmtTime(p.event.ts)}</div>
      <div className={`pet-score score--${b}`}>
        {b} {p.event.score >= 0 ? "+" : ""}{p.event.score.toFixed(2)}
      </div>
      <div className="pet-title">{p.event.title}</div>
      {p.event.url && (
        <a href={p.event.url} target="_blank" rel="noopener noreferrer" className="pet-link">
          Open article →
        </a>
      )}
    </div>
  );
}

export default function PricePanel({
  ticker, onClose,
}: { ticker: string; onClose: () => void }) {
  const [prices, setPrices] = useState<PriceRow[]>([]);
  const [events, setEvents] = useState<EventRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true); setErr(null);
    fetch(`${API_BASE}/prices/${ticker}?days=7`)
      .then((r) => r.json())
      .then((d) => {
        if (!alive) return;
        setPrices(d.prices ?? []);
        setEvents(d.events ?? []);
        setLoading(false);
      })
      .catch((e) => { if (alive) { setErr(String(e)); setLoading(false); } });
    return () => { alive = false; };
  }, [ticker]);

  // Merge into a single time-ordered series. Price points carry `close`,
  // event points carry `event`. Recharts renders the line by skipping null
  // closes (connectNulls) and the scatter only plots non-null events.
  const series = useMemo(() => {
    type Row = { ts: string; close: number | null; event: EventRow | null };
    const rows: Row[] = [
      ...prices.map<Row>((p) => ({ ts: p.ts, close: p.close, event: null })),
      ...events.map<Row>((e) => ({ ts: e.ts, close: null,     event: e   })),
    ];
    rows.sort((a, b) => String(a.ts).localeCompare(String(b.ts)));
    return rows;
  }, [prices, events]);

  const first = prices[0]?.close;
  const last  = prices[prices.length - 1]?.close;
  const delta = first && last ? ((last - first) / first) * 100 : null;

  const bullish = events.filter((e) => bucketOf(e.score) === "bullish").length;
  const bearish = events.filter((e) => bucketOf(e.score) === "bearish").length;

  return (
    <aside className="price-panel" role="complementary" aria-label={`Price correlation for ${ticker}`}>
      <header className="price-panel-head">
        <div>
          <div className="price-panel-ticker">{ticker}</div>
          <div className="price-panel-sub">
            {prices.length > 0 ? (
              <>
                ${last?.toFixed(2)}
                {delta != null && (
                  <span className={`price-panel-delta ${delta >= 0 ? "up" : "down"}`}>
                    {delta >= 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(2)}% (7d)
                  </span>
                )}
              </>
            ) : (
              "No price data yet"
            )}
          </div>
        </div>
        <button className="price-panel-close" onClick={onClose} aria-label="Close">✕</button>
      </header>

      {loading ? (
        <div className="price-panel-empty">Loading…</div>
      ) : err ? (
        <div className="price-panel-empty">Failed: {err}</div>
      ) : prices.length === 0 ? (
        <div className="price-panel-empty">
          No price data for {ticker} yet. The price poller runs every 5 minutes.
          First fetch may take a moment after the ticker appears in a news item.
        </div>
      ) : (
        <>
          <div className="price-panel-chart">
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={series} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
                <XAxis
                  dataKey="ts"
                  stroke="#55627a"
                  tick={{ fontSize: 10 }}
                  tickFormatter={(v) => fmtDay(String(v))}
                  minTickGap={40}
                />
                <YAxis
                  yAxisId="price"
                  stroke="#55627a"
                  tick={{ fontSize: 10 }}
                  domain={["auto", "auto"]}
                  tickFormatter={(v) => `$${Number(v).toFixed(0)}`}
                />
                <YAxis
                  yAxisId="sentiment"
                  orientation="right"
                  domain={[-1, 1]}
                  ticks={[-1, -0.5, 0, 0.5, 1]}
                  stroke="#55627a"
                  tick={{ fontSize: 10 }}
                  tickFormatter={(v) => Number(v).toFixed(1)}
                />
                <Tooltip content={<EventTooltip />} contentStyle={TOOLTIP_STYLE} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line
                  yAxisId="price"
                  type="monotone"
                  dataKey="close"
                  name="Price"
                  stroke="#22d3ee"
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                  isAnimationActive={false}
                />
                <Scatter
                  yAxisId="sentiment"
                  dataKey="event.score"
                  name="News sentiment"
                  shape={(props: any) => {
                    const { cx, cy, payload } = props;
                    if (!payload?.event) return <g />;
                    const b = bucketOf(payload.event.score);
                    return (
                      <circle
                        cx={cx} cy={cy} r={5}
                        fill={COLORS[b]}
                        stroke="#05060a"
                        strokeWidth={1.5}
                        style={{ filter: `drop-shadow(0 0 6px ${COLORS[b]})` }}
                      />
                    );
                  }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          <div className="price-panel-stats">
            <div className="pp-stat"><span>Events 7d</span><strong>{events.length}</strong></div>
            <div className="pp-stat pp-stat--bullish"><span>Bullish</span><strong>{bullish}</strong></div>
            <div className="pp-stat pp-stat--bearish"><span>Bearish</span><strong>{bearish}</strong></div>
          </div>

          <div className="price-panel-events">
            <div className="price-panel-events-head">Events on this ticker</div>
            <ul>
              {events.slice().reverse().slice(0, 12).map((e) => {
                const b = bucketOf(e.score);
                return (
                  <li key={e.news_id} className={`pp-event pp-event--${b}`}>
                    <span className="pp-event-time">{fmtTime(e.ts)}</span>
                    <span className="pp-event-title">
                      {e.url ? <a href={e.url} target="_blank" rel="noopener noreferrer">{e.title}</a> : e.title}
                    </span>
                    <span className={`pp-event-score score--${b}`}>
                      {e.score >= 0 ? "+" : ""}{e.score.toFixed(2)}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        </>
      )}
    </aside>
  );
}