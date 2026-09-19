import { AnimatePresence, motion } from "framer-motion";
import { forwardRef, useMemo, useRef, useState, type ReactNode } from "react";
import type { NewsItem } from "../App";
import CompanyHoverCard from "./CompanyHoverCard";
import {
  formatRelativeTime, formatScore, getSentimentBucket,
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

function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

type NewsCardProps = {
  item: NewsItem;
  isNew: boolean;
  onSelectTicker: (ticker: string) => void;
};

const NewsCard = forwardRef<HTMLElement, NewsCardProps>(function NewsCard(
  { item, isNew, onSelectTicker },
  ref,
) {
  const bucket = getSentimentBucket(item.score);
  const footerEntityRef = useRef<HTMLSpanElement | null>(null);
  const [hoverState, setHoverState] = useState<{ ticker: string; rect: DOMRect } | null>(null);
  const timerRef = useRef<number | null>(null);

  const hasTicker = Boolean(item.ticker && item.ticker.trim());

  const cancelHide = () => {
    if (timerRef.current) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  const showHover = (ticker: string, rect: DOMRect) => {
    cancelHide();
    timerRef.current = window.setTimeout(() => {
      setHoverState({ ticker, rect });
    }, 120);
  };

  const hideHover = () => {
    cancelHide();
    timerRef.current = window.setTimeout(() => {
      setHoverState(null);
    }, 350);
  };

  const toggleHover = (ticker: string, rect: DOMRect) => {
    cancelHide();
    setHoverState((prev) => (prev?.ticker === ticker ? null : { ticker, rect }));
  };

  // Compile list of known company targets mentioned in this article
  const companyTargets = useMemo(() => {
    const list: { name: string; ticker: string }[] = [];
    if (item.companies && item.companies.length > 0) {
      for (const c of item.companies) {
        if (c.name && c.ticker) list.push({ name: c.name, ticker: c.ticker });
      }
    } else if (item.company && item.ticker) {
      list.push({ name: item.company, ticker: item.ticker });
    }
    // Sort descending by name length to match longer names first ("Apple Inc" before "Apple")
    list.sort((a, b) => b.name.length - a.name.length);
    return list;
  }, [item.companies, item.company, item.ticker]);

  // Tokenize title: replaces company mentions with interactive [Company] tokens
  const renderedTitle = useMemo((): ReactNode => {
    if (companyTargets.length === 0) {
      return item.url ? (
        <a href={item.url} target="_blank" rel="noopener noreferrer">
          {item.title}
        </a>
      ) : (
        item.title
      );
    }

    const escapedPatterns: string[] = [];
    for (const t of companyTargets) {
      if (t.name) escapedPatterns.push(escapeRegex(t.name));
      if (t.ticker && t.ticker.length >= 2) escapedPatterns.push(escapeRegex(t.ticker));
    }

    if (escapedPatterns.length === 0) {
      return item.url ? (
        <a href={item.url} target="_blank" rel="noopener noreferrer">
          {item.title}
        </a>
      ) : (
        item.title
      );
    }

    const regex = new RegExp(`\\b(${escapedPatterns.join("|")})\\b`, "gi");
    const segments = item.title.split(regex);

    const inlineNodes = segments.map((seg, i) => {
      const segLower = seg.toLowerCase();
      const matched = companyTargets.find(
        (t) => t.name.toLowerCase() === segLower || t.ticker.toLowerCase() === segLower
      );

      if (!matched) {
        return seg;
      }

      return (
        <span
          key={`token-${i}`}
          className="company-token"
          onMouseEnter={(e) => showHover(matched.ticker, e.currentTarget.getBoundingClientRect())}
          onMouseLeave={hideHover}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            toggleHover(matched.ticker, e.currentTarget.getBoundingClientRect());
          }}
          tabIndex={0}
          role="button"
          aria-label={`View intelligence card for ${matched.name} (${matched.ticker})`}
        >
          [{seg}]
        </span>
      );
    });

    if (item.url) {
      return (
        <a href={item.url} target="_blank" rel="noopener noreferrer">
          {inlineNodes}
        </a>
      );
    }
    return inlineNodes;
  }, [item.title, item.url, companyTargets]);

  return (
    <motion.article
      ref={ref}
      initial={{ opacity: 0, y: -12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, x: -24, transition: { duration: 0.15 } }}
      transition={{ type: "spring", stiffness: 340, damping: 30 }}
      className={`news-card news-card--${bucket}${isNew ? " is-new" : ""}`}
      role="article"
      aria-label={`${LABELS[bucket]}: ${item.title}`}
      onMouseLeave={hideHover}
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

        <h3 className="news-title">{renderedTitle}</h3>

        <footer className="news-footer">
          <span
            ref={footerEntityRef}
            className={`entity${hasTicker ? " entity--interactive" : ""}`}
            onMouseEnter={() => {
              if (hasTicker && footerEntityRef.current) {
                showHover(item.ticker!, footerEntityRef.current.getBoundingClientRect());
              }
            }}
            onMouseLeave={hideHover}
            onClick={() => {
              if (hasTicker && footerEntityRef.current) {
                toggleHover(item.ticker!, footerEntityRef.current.getBoundingClientRect());
              }
            }}
            tabIndex={hasTicker ? 0 : -1}
            role={hasTicker ? "button" : undefined}
            aria-label={hasTicker ? `View company intelligence for ${item.ticker}` : undefined}
          >
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

      {hoverState && (
        <CompanyHoverCard
          ticker={hoverState.ticker}
          anchorRect={hoverState.rect}
          onOpenPanel={(t) => {
            setHoverState(null);
            onSelectTicker(t);
          }}
          onClose={() => setHoverState(null)}
          onMouseEnter={cancelHide}
          onMouseLeave={hideHover}
        />
      )}
    </motion.article>
  );
});

export default function NewsStream({
  news, newIds, onSelectTicker,
}: {
  news: NewsItem[];
  newIds: Set<string>;
  onSelectTicker: (ticker: string) => void;
}) {
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
        <span>Live Intelligence Feed</span>
        <span className="panel-meta panel-meta--live">
          <span className="panel-meta-dot" aria-hidden="true" />
          {filtered.length} events
        </span>
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
          <AnimatePresence initial={false}>
            {filtered.map((item) => (
              <NewsCard
                key={item.id}
                item={item}
                isNew={newIds.has(item.id)}
                onSelectTicker={onSelectTicker}
              />
            ))}
          </AnimatePresence>
        )}
      </div>
    </section>
  );
}