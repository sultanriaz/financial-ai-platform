import { useEffect, useRef, useState } from "react";
import { API_BASE } from "../config";

export interface RelatedNewsItem {
  id: string;
  title: string;
  url?: string;
  source?: string;
  sentiment?: string;
  score?: number;
  timestamp?: string | null;
}

export interface CompanyProfile {
  name: string;
  ticker: string;
  price: number | null;
  change_percent: number | null;
  market_cap: string;
  sector: string;
  industry?: string | null;
  exchange?: string | null;
  pe_ratio?: number | null;
  sentiment_score?: number | null;
  related_news?: RelatedNewsItem[];
  sparkline?: { ts: string; close: number }[];
}

const CACHE_TTL_MS = 60_000; // 60 seconds TTL
const cache = new Map<string, { data: CompanyProfile; timestamp: number }>();
const pending = new Map<string, Promise<CompanyProfile>>();

/**
 * Fetch company profile with in-memory caching and request deduplication.
 */
export async function getCompanyProfile(ticker: string): Promise<CompanyProfile> {
  const sym = (ticker || "").trim().toUpperCase().replace(".", "-");
  if (!sym) {
    throw new Error("Invalid ticker symbol");
  }

  // Check cache
  const cached = cache.get(sym);
  if (cached && Date.now() - cached.timestamp < CACHE_TTL_MS) {
    return cached.data;
  }

  // Deduplicate concurrent requests
  if (pending.has(sym)) {
    return pending.get(sym)!;
  }

  const req = (async () => {
    try {
      const res = await fetch(`${API_BASE}/api/company/${encodeURIComponent(sym)}`);
      if (!res.ok) {
        throw new Error(`Server returned HTTP ${res.status}`);
      }
      const data: CompanyProfile = await res.json();
      cache.set(sym, { data, timestamp: Date.now() });
      return data;
    } finally {
      pending.delete(sym);
    }
  })();

  pending.set(sym, req);
  return req;
}

/**
 * React hook to retrieve company intelligence with loading, error, and cached states.
 */
export function useCompanyProfile(ticker: string | null) {
  const [data, setData] = useState<CompanyProfile | null>(() => {
    if (!ticker) return null;
    const hit = cache.get(ticker.toUpperCase());
    return hit && Date.now() - hit.timestamp < CACHE_TTL_MS ? hit.data : null;
  });
  const [loading, setLoading] = useState<boolean>(!data && Boolean(ticker));
  const [error, setError] = useState<string | null>(null);
  const activeTickerRef = useRef<string | null>(ticker);

  useEffect(() => {
    activeTickerRef.current = ticker;
    if (!ticker) {
      setData(null);
      setLoading(false);
      setError(null);
      return;
    }

    const sym = ticker.trim().toUpperCase();
    const hit = cache.get(sym);
    if (hit && Date.now() - hit.timestamp < CACHE_TTL_MS) {
      setData(hit.data);
      setLoading(false);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);

    let isMounted = true;
    getCompanyProfile(sym)
      .then((profile) => {
        if (isMounted && activeTickerRef.current === ticker) {
          setData(profile);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted && activeTickerRef.current === ticker) {
          setError(err instanceof Error ? err.message : "Failed to load company profile");
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [ticker]);

  return { data, loading, error, refetch: () => ticker && getCompanyProfile(ticker) };
}
