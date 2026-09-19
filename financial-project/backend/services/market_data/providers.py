import os
import logging
import httpx
from typing import Any
from services.market_data.base import BaseMarketDataProvider
from services.market_data.yfinance_provider import YFinanceProvider
from services.market_data.mock_provider import MockMarketDataProvider

logger = logging.getLogger("market-providers")


class AlphaVantageProvider(BaseMarketDataProvider):
    """Provider for Alpha Vantage API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY", "")

    async def get_profile(self, ticker: str) -> dict[str, Any] | None:
        if not self.api_key:
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Overview
                url_ov = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={self.api_key}"
                r_ov = await client.get(url_ov)
                ov = r_ov.json() if r_ov.status_code == 200 else {}

                # Global Quote
                url_q = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={self.api_key}"
                r_q = await client.get(url_q)
                q_data = r_q.json().get("Global Quote", {}) if r_q.status_code == 200 else {}

                price = float(q_data.get("05. price", 0)) or None
                change_pct_str = q_data.get("10. change percent", "0%").replace("%", "")
                change_pct = float(change_pct_str) if change_pct_str else 0.0

                if not price:
                    return None

                return {
                    "name": ov.get("Name", ticker),
                    "ticker": ticker.upper(),
                    "price": round(price, 2),
                    "change_percent": round(change_pct, 2),
                    "market_cap": ov.get("MarketCapitalization", "N/A"),
                    "sector": ov.get("Sector", "Unknown"),
                    "industry": ov.get("Industry"),
                    "pe_ratio": float(ov.get("PERatio", 0)) if ov.get("PERatio") else None,
                    "exchange": ov.get("Exchange"),
                    "sparkline": []
                }
        except Exception as exc:
            logger.warning("AlphaVantage fetch error for %s: %s", ticker, exc)
            return None

    async def search_ticker(self, company_name: str) -> str | None:
        if not self.api_key:
            return None
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                url = f"https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords={company_name}&apikey={self.api_key}"
                res = await client.get(url)
                if res.status_code == 200:
                    matches = res.json().get("bestMatches", [])
                    if matches:
                        return matches[0].get("1. symbol")
        except Exception:
            pass
        return None


class FinnhubProvider(BaseMarketDataProvider):
    """Provider for Finnhub Stock API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("FINNHUB_API_KEY", "")

    async def get_profile(self, ticker: str) -> dict[str, Any] | None:
        if not self.api_key:
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {"X-Finnhub-Token": self.api_key}
                p_resp = await client.get(f"https://finnhub.io/api/v1/stock/profile2?symbol={ticker}", headers=headers)
                q_resp = await client.get(f"https://finnhub.io/api/v1/quote?symbol={ticker}", headers=headers)

                prof = p_resp.json() if p_resp.status_code == 200 else {}
                quote = q_resp.json() if q_resp.status_code == 200 else {}

                price = quote.get("c")
                if not price:
                    return None

                change_pct = quote.get("dp", 0.0)
                mcap = prof.get("marketCapitalization")
                mcap_str = f"{mcap / 1000:.1f}B" if mcap else "N/A"

                return {
                    "name": prof.get("name", ticker),
                    "ticker": ticker.upper(),
                    "price": round(float(price), 2),
                    "change_percent": round(float(change_pct), 2),
                    "market_cap": mcap_str,
                    "sector": prof.get("finnhubIndustry", "Unknown"),
                    "industry": prof.get("finnhubIndustry"),
                    "pe_ratio": None,
                    "exchange": prof.get("exchange"),
                    "sparkline": []
                }
        except Exception as exc:
            logger.warning("Finnhub fetch error for %s: %s", ticker, exc)
            return None

    async def search_ticker(self, company_name: str) -> str | None:
        if not self.api_key:
            return None
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                headers = {"X-Finnhub-Token": self.api_key}
                resp = await client.get(f"https://finnhub.io/api/v1/search?q={company_name}", headers=headers)
                if resp.status_code == 200:
                    results = resp.json().get("result", [])
                    if results:
                        return results[0].get("symbol")
        except Exception:
            pass
        return None


class PolygonProvider(BaseMarketDataProvider):
    """Provider for Polygon.io API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("POLYGON_API_KEY", "")

    async def get_profile(self, ticker: str) -> dict[str, Any] | None:
        if not self.api_key:
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                d_resp = await client.get(f"https://api.polygon.io/v3/reference/tickers/{ticker}", headers=headers)
                p_resp = await client.get(f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev", headers=headers)

                detail = d_resp.json().get("results", {}) if d_resp.status_code == 200 else {}
                prev = p_resp.json().get("results", [{}])[0] if p_resp.status_code == 200 else {}

                price = prev.get("c")
                open_p = prev.get("o")
                change_pct = round(((price - open_p) / open_p) * 100, 2) if price and open_p else 0.0

                if not price:
                    return None

                mcap = detail.get("market_cap")
                mcap_str = f"{mcap / 1e12:.1f}T" if mcap and mcap >= 1e12 else f"{mcap / 1e9:.1f}B" if mcap else "N/A"

                return {
                    "name": detail.get("name", ticker),
                    "ticker": ticker.upper(),
                    "price": round(float(price), 2),
                    "change_percent": change_pct,
                    "market_cap": mcap_str,
                    "sector": detail.get("sic_description", "Unknown"),
                    "industry": None,
                    "pe_ratio": None,
                    "exchange": detail.get("primary_exchange"),
                    "sparkline": []
                }
        except Exception as exc:
            logger.warning("Polygon fetch error for %s: %s", ticker, exc)
            return None

    async def search_ticker(self, company_name: str) -> str | None:
        return None


class FallbackCompositeProvider(BaseMarketDataProvider):
    """
    Chains providers: primary (yfinance or configured API) -> mock/synthetic fallback.
    Ensures zero failure rate for the user interface.
    """

    def __init__(self, primary: BaseMarketDataProvider, fallback: BaseMarketDataProvider):
        self.primary = primary
        self.fallback = fallback

    async def get_profile(self, ticker: str) -> dict[str, Any] | None:
        try:
            prof = await self.primary.get_profile(ticker)
            if prof and prof.get("price") is not None:
                return prof
        except Exception as e:
            logger.info("Primary provider failed for %s (%s); trying fallback", ticker, e)

        return await self.fallback.get_profile(ticker)

    async def search_ticker(self, company_name: str) -> str | None:
        try:
            t = await self.primary.search_ticker(company_name)
            if t:
                return t
        except Exception:
            pass
        return await self.fallback.search_ticker(company_name)


def create_market_data_provider() -> BaseMarketDataProvider:
    """Factory creating the configured provider with automatic fallback."""
    provider_name = os.getenv("MARKET_DATA_PROVIDER", "yfinance").lower()
    fallback = MockMarketDataProvider()

    primary: BaseMarketDataProvider
    if provider_name == "alphavantage" and os.getenv("ALPHA_VANTAGE_API_KEY"):
        primary = AlphaVantageProvider()
    elif provider_name == "finnhub" and os.getenv("FINNHUB_API_KEY"):
        primary = FinnhubProvider()
    elif provider_name == "polygon" and os.getenv("POLYGON_API_KEY"):
        primary = PolygonProvider()
    else:
        primary = YFinanceProvider()

    return FallbackCompositeProvider(primary=primary, fallback=fallback)
