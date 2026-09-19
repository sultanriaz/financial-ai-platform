// FIX #6: single source of truth for sentiment bucketing.
// Analytics.tsx was using ±0.15; NewsStream.tsx was using >= 0 (sign only).
// Both now import from here so the threshold is identical everywhere.
export const SENTIMENT_THRESHOLD = 0.15;

export type SentimentBucket = "bullish" | "neutral" | "bearish";

export function getSentimentBucket(score: number | null | undefined): SentimentBucket {
  if (score == null)              return "neutral";
  if (score >  SENTIMENT_THRESHOLD) return "bullish";
  if (score < -SENTIMENT_THRESHOLD) return "bearish";
  return "neutral";
}

export function formatScore(score: number | null | undefined): string {
  if (score == null) return "—";
  return `${score >= 0 ? "+" : ""}${score.toFixed(2)}`;
}

export function formatRelativeTime(isoString: string | null | undefined): string {
  if (!isoString) return "";
  const diff = Date.now() - new Date(isoString).getTime();
  if (diff < 60_000)       return "just now";
  if (diff < 3_600_000)    return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000)   return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}
