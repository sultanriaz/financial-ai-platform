import asyncio
import logging
from typing import Any
from services.market_data.base import BaseMarketDataProvider

logger = logging.getLogger("yfinance-provider")


def format_market_cap(val: float | int | None) -> str:
    if val is None or val <= 0:
        return "N/A"
    if val >= 1e12:
        return f"{val / 1e12:.1f}T"
    if val >= 1e9:
        return f"{val / 1e9:.1f}B"
    if val >= 1e6:
        return f"{val / 1e6:.1f}M"
    return f"{val:,.0f}"


class YFinanceProvider(BaseMarketDataProvider):
    """Fetches real-time company profiles and statistics using Yahoo Finance (yfinance)."""

    def _fetch_blocking(self, ticker: str) -> dict[str, Any] | None:
        import yfinance as yf
        try:
            t = yf.Ticker(ticker)
            info = {}
            try:
                info = t.info or {}
            except Exception as e:
                logger.debug("Failed to fetch full info for %s: %s", ticker, e)

            fast_info = getattr(t, "fast_info", {})

            # Extract price
            price = None
            for k in ("last_price", "regular_market_price", "lastPrice", "regularMarketPrice", "currentPrice"):
                if hasattr(fast_info, k) and getattr(fast_info, k) is not None:
                    price = float(getattr(fast_info, k))
                    break
                if isinstance(info, dict) and info.get(k) is not None:
                    price = float(info[k])
                    break

            # Previous close & change percent
            prev_close = getattr(fast_info, "previous_close", None) or (info.get("previousClose") if isinstance(info, dict) else None)
            change_percent = None
            if price is not None and prev_close:
                try:
                    change_percent = round(((price - float(prev_close)) / float(prev_close)) * 100, 2)
                except Exception:
                    pass
            elif isinstance(info, dict) and info.get("regularMarketChangePercent") is not None:
                change_percent = round(float(info["regularMarketChangePercent"]), 2)

            # Market cap
            mcap_raw = getattr(fast_info, "market_cap", None) or (info.get("marketCap") if isinstance(info, dict) else None)
            mcap_str = format_market_cap(mcap_raw)

            # PE ratio
            pe = None
            if isinstance(info, dict):
                pe_raw = info.get("trailingPE") or info.get("forwardPE")
                if pe_raw is not None:
                    pe = round(float(pe_raw), 2)

            # Sparkline from 7-day history
            sparkline = []
            try:
                hist = t.history(period="7d", interval="1h")
                if hist is not None and not hist.empty:
                    for idx, row in hist.iterrows():
                        sparkline.append({
                            "ts": idx.isoformat() if hasattr(idx, "isoformat") else str(idx),
                            "close": round(float(row["Close"]), 2)
                        })
            except Exception as e:
                logger.debug("Sparkline fetch error for %s: %s", ticker, e)

            name = (
                (info.get("shortName") or info.get("longName"))
                if isinstance(info, dict)
                else None
            ) or ticker

            sector = (info.get("sector") if isinstance(info, dict) else None) or "Technology"
            industry = info.get("industry") if isinstance(info, dict) else None
            exchange = (
                getattr(fast_info, "exchange", None)
                or (info.get("exchange") if isinstance(info, dict) else None)
            )

            if price is None:
                # If yfinance returned empty price, return None to let fallback kick in
                return None

            return {
                "name": name,
                "ticker": ticker.upper(),
                "price": round(price, 2),
                "change_percent": change_percent if change_percent is not None else 0.0,
                "market_cap": mcap_str,
                "sector": sector,
                "industry": industry,
                "pe_ratio": pe,
                "exchange": exchange,
                "sparkline": sparkline[-30:] if sparkline else []
            }
        except Exception as exc:
            logger.warning("YFinance fetch exception for %s: %s", ticker, exc)
            return None

    async def get_profile(self, ticker: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._fetch_blocking, ticker)

    async def search_ticker(self, company_name: str) -> str | None:
        # yfinance doesn't have an official search API, so resolution is handled by CompanyService mappings
        return None
