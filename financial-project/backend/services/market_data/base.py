from abc import ABC, abstractmethod
from typing import Any

class BaseMarketDataProvider(ABC):
    """Abstract base class for financial market data providers."""

    @abstractmethod
    async def get_profile(self, ticker: str) -> dict[str, Any] | None:
        """
        Fetch company profile and live market statistics.
        Returns:
            {
                "name": str,
                "ticker": str,
                "price": float,
                "change_percent": float,
                "market_cap": str,
                "sector": str,
                "industry": str | None,
                "pe_ratio": float | None,
                "exchange": str | None,
                "sparkline": list[dict] | None
            }
        """
        pass

    @abstractmethod
    async def search_ticker(self, company_name: str) -> str | None:
        """Resolve a company name or query to a primary stock ticker symbol."""
        pass
