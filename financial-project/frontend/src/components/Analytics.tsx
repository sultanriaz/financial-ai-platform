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
        <div className="panel-heading">
          <span>Sentiment Distribution</span>
          <span className="panel-meta panel-meta--info">
            {news.length} signals
          </span>
        </div>
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
          <div className="panel-heading">
            <span>Sentiment Timeline</span>
            <span className="panel-meta">{timeSeries.length}h window</span>
          </div>
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