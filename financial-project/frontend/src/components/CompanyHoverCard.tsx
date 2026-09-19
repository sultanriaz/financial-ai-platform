import { motion } from "framer-motion";
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { Line, LineChart, ResponsiveContainer } from "recharts";
import { useCompanyProfile } from "../api/companyApi";

interface CompanyHoverCardProps {
  ticker: string;
  anchorRect: DOMRect;
  onOpenPanel: (ticker: string) => void;
  onClose?: () => void;
  onMouseEnter?: () => void;
  onMouseLeave?: () => void;
}

export default function CompanyHoverCard({
  ticker,
  anchorRect,
  onOpenPanel,
  onClose,
  onMouseEnter,
  onMouseLeave,
}: CompanyHoverCardProps) {
  const { data, loading, error, refetch } = useCompanyProfile(ticker);
  const cardRef = useRef<HTMLDivElement | null>(null);

  // Close when clicking outside on mobile or touch
  useEffect(() => {
    function handleClickOutside(e: MouseEvent | TouchEvent) {
      if (cardRef.current && !cardRef.current.contains(e.target as Node)) {
        onClose?.();
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("touchstart", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("touchstart", handleClickOutside);
    };
  }, [onClose]);

  // Viewport-aware positioning with clean distance from hover anchor
  const cardW = 310;
  const estCardH = 340;
  const padding = 12;
  const DISTANCE = 14; // Visible distance from hovering point

  // Horizontal clamping, aligned with a slight offset
  const left = Math.min(
    Math.max(padding, anchorRect.left - 6),
    window.innerWidth - cardW - padding
  );

  // Vertical flip if not enough space below
  const spaceBelow = window.innerHeight - anchorRect.bottom;
  const placeAbove = spaceBelow < (estCardH + DISTANCE) && anchorRect.top > (estCardH + DISTANCE);
  const top = placeAbove
    ? Math.max(padding, anchorRect.top - estCardH - DISTANCE)
    : Math.min(anchorRect.bottom + DISTANCE, window.innerHeight - estCardH - padding);

  const change = data?.change_percent ?? null;
  const isPositive = change != null && change >= 0;
  const changeClass = change == null ? "" : isPositive ? "up" : "down";

  // Derive sentiment label and impact percentage
  const sentimentScore = data?.sentiment_score ?? 0.82;
  const sentimentLabel =
    sentimentScore >= 0.2 ? "Positive" : sentimentScore <= -0.2 ? "Negative" : "Neutral";
  const sentimentClass =
    sentimentScore >= 0.2 ? "bullish" : sentimentScore <= -0.2 ? "bearish" : "neutral";
  const newsImpactPct = Math.round(Math.min(100, Math.max(10, Math.abs(sentimentScore) * 100)));

  const sparklineData = data?.sparkline ?? [];

  const cardNode = (
    <motion.div
      ref={cardRef}
      data-placement={placeAbove ? "top" : "bottom"}
      initial={{ opacity: 0, scale: 0.96, y: placeAbove ? 6 : -6 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.96, transition: { duration: 0.12 } }}
      transition={{ type: "spring", stiffness: 420, damping: 32 }}
      className="company-hover-card"
      style={{
        position: "fixed",
        left,
        top,
        width: cardW,
      }}
      role="dialog"
      aria-label={`Company intelligence for ${data?.name ?? ticker}`}
      onClick={(e) => e.stopPropagation()}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      {/* Header bar */}
      <header className="hover-card-head">
        <div className="hover-card-head-info">
          <div className="hover-card-ticker-row">
            <span className="hover-card-name">
              {data?.name ?? ticker}
            </span>
            <span className="hover-card-ticker-pill">({ticker})</span>
          </div>
          <span className="hover-card-exchange">{data?.exchange ?? "Market Intelligence"}</span>
        </div>

        {onClose && (
          <button
            className="hover-card-close-btn"
            onClick={onClose}
            aria-label="Close hover card"
          >
            ×
          </button>
        )}
      </header>

      {/* Loading State */}
      {loading && !data && (
        <div className="hover-card-loading-skeleton" aria-live="polite">
          <div className="skeleton-line skeleton-title" />
          <div className="skeleton-grid">
            <div className="skeleton-box" />
            <div className="skeleton-box" />
            <div className="skeleton-box" />
            <div className="skeleton-box" />
          </div>
          <div className="skeleton-chart" />
        </div>
      )}

      {/* Error State */}
      {error && !data && (
        <div className="hover-card-error-state">
          <p className="hover-card-error-msg">{error}</p>
          <button
            className="hover-card-retry-btn"
            onClick={() => refetch()}
          >
            Retry
          </button>
        </div>
      )}

      {/* Content State */}
      {data && (
        <>
          {/* Live Price & Change */}
          <div className="hover-card-price-hero">
            <div className="hover-card-main-price">
              {data.price != null ? `$${data.price.toFixed(2)}` : "—"}
            </div>
            {change != null && (
              <span className={`hover-card-change-badge ${changeClass}`}>
                {isPositive ? "▲" : "▼"} {isPositive ? "+" : ""}{change.toFixed(1)}%
              </span>
            )}
          </div>

          {/* Key Financial Statistics Grid */}
          <div className="hover-card-stats-grid">
            <div className="hover-stat-card">
              <span className="hover-stat-label">Market Cap</span>
              <span className="hover-stat-val">{data.market_cap || "—"}</span>
            </div>
            <div className="hover-stat-card">
              <span className="hover-stat-label">Sector</span>
              <span className="hover-stat-val truncate" title={data.sector}>
                {data.sector || "Technology"}
              </span>
            </div>
            <div className="hover-stat-card">
              <span className="hover-stat-label">P/E Ratio</span>
              <span className="hover-stat-val">
                {data.pe_ratio != null ? data.pe_ratio.toFixed(1) : "—"}
              </span>
            </div>
            <div className="hover-stat-card">
              <span className="hover-stat-label">AI Sentiment</span>
              <span className={`hover-stat-val hover-stat--${sentimentClass}`}>
                {sentimentLabel}
              </span>
            </div>
            <div className="hover-stat-card full-width">
              <span className="hover-stat-label">News Impact</span>
              <div className="impact-bar-wrapper">
                <span className="hover-stat-val">{newsImpactPct}%</span>
                <div className="impact-track">
                  <div
                    className={`impact-fill impact-fill--${sentimentClass}`}
                    style={{ width: `${newsImpactPct}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Recent Movement Sparkline */}
          <div className="hover-card-movement-section">
            <span className="hover-movement-label">Recent movement</span>
            <div className="hover-card-spark">
              {sparklineData.length > 1 ? (
                <ResponsiveContainer width="100%" height={42}>
                  <LineChart data={sparklineData} margin={{ top: 2, bottom: 2, left: 2, right: 2 }}>
                    <Line
                      type="monotone"
                      dataKey="close"
                      stroke={isPositive ? "#34d399" : "#f43f5e"}
                      strokeWidth={1.8}
                      dot={false}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="hover-spark-placeholder">
                  <div className="hover-spark-flat" />
                </div>
              )}
            </div>
          </div>

          {/* Action CTA */}
          <button
            className="hover-card-cta"
            onClick={(e) => {
              e.stopPropagation();
              onOpenPanel(ticker);
            }}
          >
            View price correlation →
          </button>
        </>
      )}
    </motion.div>
  );

  return createPortal(cardNode, document.body);
}