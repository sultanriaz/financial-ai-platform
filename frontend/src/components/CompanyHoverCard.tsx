import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Line, LineChart, ResponsiveContainer } from "recharts";

type Summary = {
  ticker: string;
  company: string;
  mentions_24h: number;
  mentions_7d: number;
  avg_score_24h: number;
  avg_score_7d: number;
  latest_price: number | null;
  change_pct: number | null;
  sparkline: { ts: string; close: number }[];
};

const cache = new Map<string, { at: number; data: Summary }>();
const CACHE_MS = 30_000;

async function fetchSummary(ticker: string): Promise<Summary | null> {
  const hit = cache.get(ticker);
  if (hit && Date.now() - hit.at < CACHE_MS) return hit.data;
  try {
    const r = await fetch(`http://localhost:8001/companies/${ticker}/summary`);
    if (!r.ok) return null;
    const data: Summary = await r.json();
    cache.set(ticker, { at: Date.now(), data });
    return data;
  } catch {
    return null;
  }
}

function bucketFromScore(s: number) {
  if (s >  0.15) return "bullish";
  if (s < -0.15) return "bearish";
  return "neutral";
}

export default function CompanyHoverCard({
  ticker,
  anchorRect,
  onOpenPanel,
}: {
  ticker: string;
  anchorRect: DOMRect;
  onOpenPanel: (ticker: string) => void;
}) {
  const [data, setData] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    fetchSummary(ticker).then((d) => { if (alive) { setData(d); setLoading(false); } });
    return () => { alive = false; };
  }, [ticker]);

  const bucket = data ? bucketFromScore(data.avg_score_24h) : "neutral";
  const change = data?.change_pct ?? null;
  const changeClass = change == null ? "" : change >= 0 ? "up" : "down";

  // Position below the anchor, clamped to viewport
  const cardW = 280;
  const left = Math.min(Math.max(8, anchorRect.left), window.innerWidth - cardW - 8);
  const top  = anchorRect.bottom + 8;

  const node = (
    <div
      className="company-hover-card"
      style={{ position: "fixed", left, top, width: cardW }}
      role="tooltip"
    >
      {loading ? (
        <div className="hover-card-loading">Loading…</div>
      ) : !data ? (
        <div className="hover-card-loading">No data</div>
      ) : (
        <>
          <header className="hover-card-head">
            <div>
              <div className="hover-card-ticker">{data.ticker}</div>
              <div className="hover-card-company">{data.company}</div>
            </div>
            <div className={`hover-card-price ${changeClass}`}>
              {data.latest_price != null ? `$${data.latest_price.toFixed(2)}` : "—"}
              {change != null && (
                <span className="hover-card-change">
                  {change >= 0 ? "▲" : "▼"} {Math.abs(change).toFixed(2)}%
                </span>
              )}
            </div>
          </header>

          {data.sparkline.length > 1 && (
            <div className="hover-card-spark">
              <ResponsiveContainer width="100%" height={38}>
                <LineChart data={data.sparkline}>
                  <Line
                    type="monotone"
                    dataKey="close"
                    stroke={change != null && change >= 0 ? "#34d399" : "#f43f5e"}
                    strokeWidth={1.6}
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="hover-card-stats">
            <div className="hover-stat">
              <span className="hover-stat-label">Mentions 24h</span>
              <span className="hover-stat-value">{data.mentions_24h}</span>
            </div>
            <div className="hover-stat">
              <span className="hover-stat-label">Mentions 7d</span>
              <span className="hover-stat-value">{data.mentions_7d}</span>
            </div>
            <div className={`hover-stat hover-stat--${bucket}`}>
              <span className="hover-stat-label">Avg 24h</span>
              <span className="hover-stat-value">
                {data.avg_score_24h >= 0 ? "+" : ""}{data.avg_score_24h.toFixed(2)}
              </span>
            </div>
          </div>

          <button
            className="hover-card-cta"
            onClick={(e) => { e.stopPropagation(); onOpenPanel(ticker); }}
          >
            View price correlation →
          </button>
        </>
      )}
    </div>
  );

  return createPortal(node, document.body);
}