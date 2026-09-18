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