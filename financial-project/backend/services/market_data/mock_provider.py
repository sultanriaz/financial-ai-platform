import math
from datetime import datetime, timedelta, timezone
from typing import Any
from services.market_data.base import BaseMarketDataProvider

KNOWN_PROFILES = {
    "AAPL": {
        "name": "Apple Inc.",
        "ticker": "AAPL",
        "price": 227.50,
        "change_percent": 1.8,
        "market_cap": "3.4T",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "pe_ratio": 36.5,
        "exchange": "NASDAQ",
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "ticker": "MSFT",
        "price": 448.20,
        "change_percent": 0.95,
        "market_cap": "3.3T",
        "sector": "Technology",
        "industry": "Software—Infrastructure",
        "pe_ratio": 37.2,
        "exchange": "NASDAQ",
    },
    "NVDA": {
        "name": "NVIDIA Corporation",
        "ticker": "NVDA",
        "price": 128.40,
        "change_percent": 3.42,
        "market_cap": "3.1T",
        "sector": "Technology",
        "industry": "Semiconductors",
        "pe_ratio": 54.8,
        "exchange": "NASDAQ",
    },
    "GOOGL": {
        "name": "Alphabet Inc.",
        "ticker": "GOOGL",
        "price": 182.15,
        "change_percent": -0.45,
        "market_cap": "2.2T",
        "sector": "Communication Services",
        "industry": "Internet Content & Information",
        "pe_ratio": 24.6,
        "exchange": "NASDAQ",
    },
    "AMZN": {
        "name": "Amazon.com, Inc.",
        "ticker": "AMZN",
        "price": 186.80,
        "change_percent": 1.12,
        "market_cap": "1.9T",
        "sector": "Consumer Cyclical",
        "industry": "Internet Retail",
        "pe_ratio": 41.3,
        "exchange": "NASDAQ",
    },
    "META": {
        "name": "Meta Platforms, Inc.",
        "ticker": "META",
        "price": 510.60,
        "change_percent": 2.15,
        "market_cap": "1.3T",
        "sector": "Communication Services",
        "industry": "Internet Content & Information",
        "pe_ratio": 26.8,
        "exchange": "NASDAQ",
    },
    "TSLA": {
        "name": "Tesla, Inc.",
        "ticker": "TSLA",
        "price": 248.90,
        "change_percent": -1.35,
        "market_cap": "790B",
        "sector": "Consumer Cyclical",
        "industry": "Auto Manufacturers",
        "pe_ratio": 68.4,
        "exchange": "NASDAQ",
    },
    "JPM": {
        "name": "JPMorgan Chase & Co.",
        "ticker": "JPM",
        "price": 218.40,
        "change_percent": 0.65,
        "market_cap": "620B",
        "sector": "Financial Services",
        "industry": "Banks—Diversified",
        "pe_ratio": 12.4,
        "exchange": "NYSE",
    },
    "JAZZ": {
        "name": "Jazz Pharmaceuticals plc",
        "ticker": "JAZZ",
        "price": 115.80,
        "change_percent": 2.40,
        "market_cap": "7.2B",
        "sector": "Healthcare",
        "industry": "Biotechnology",
        "pe_ratio": 14.8,
        "exchange": "NASDAQ",
    },
    "AMD": {
        "name": "Advanced Micro Devices, Inc.",
        "ticker": "AMD",
        "price": 156.20,
        "change_percent": 2.80,
        "market_cap": "252B",
        "sector": "Technology",
        "industry": "Semiconductors",
        "pe_ratio": 45.2,
        "exchange": "NASDAQ",
    },
    "MRNA": {
        "name": "Moderna, Inc.",
        "ticker": "MRNA",
        "price": 68.50,
        "change_percent": 3.10,
        "market_cap": "26.4B",
        "sector": "Healthcare",
        "industry": "Biotechnology",
        "pe_ratio": None,
        "exchange": "NASDAQ",
    },
    "HOOD": {
        "name": "Robinhood Markets, Inc.",
        "ticker": "HOOD",
        "price": 23.40,
        "change_percent": 4.20,
        "market_cap": "20.8B",
        "sector": "Financial Services",
        "industry": "Capital Markets",
        "pe_ratio": 38.5,
        "exchange": "NASDAQ",
    }
}


def generate_synthetic_sparkline(base_price: float, change_percent: float) -> list[dict]:
    now = datetime.now(timezone.utc)
    points = []
    trend = change_percent / 100.0
    start_price = base_price / (1.0 + trend) if (1.0 + trend) != 0 else base_price

    for i in range(20):
        dt = now - timedelta(hours=20 - i)
        progress = i / 19.0
        wave = math.sin(i * 0.8) * (base_price * 0.015)
        p = start_price + (base_price - start_price) * progress + wave
        points.append({
            "ts": dt.isoformat(),
            "close": round(max(1.0, p), 2)
        })
    return points


class MockMarketDataProvider(BaseMarketDataProvider):
    """High-fidelity fallback market data provider."""

    async def get_profile(self, ticker: str) -> dict[str, Any] | None:
        sym = (ticker or "").strip().upper()
        if sym in KNOWN_PROFILES:
            data = dict(KNOWN_PROFILES[sym])
            data["sparkline"] = generate_synthetic_sparkline(data["price"], data["change_percent"])
            return data

        # Deterministic generation for arbitrary tickers
        hash_val = sum(ord(c) for c in sym)
        price = round(50.0 + (hash_val % 400) + ((hash_val % 99) / 100.0), 2)
        change_pct = round(((hash_val % 11) - 5) * 0.65, 2)
        pe = round(15.0 + (hash_val % 40), 1)

        return {
            "name": f"{sym} Corporation",
            "ticker": sym,
            "price": price,
            "change_percent": change_pct,
            "market_cap": f"{10 + (hash_val % 900)}B",
            "sector": "Technology" if hash_val % 2 == 0 else "Financial Services",
            "industry": "Diversified",
            "pe_ratio": pe,
            "exchange": "NASDAQ",
            "sparkline": generate_synthetic_sparkline(price, change_pct)
        }

    async def search_ticker(self, company_name: str) -> str | None:
        name_lower = company_name.lower().strip()
        for sym, prof in KNOWN_PROFILES.items():
            if name_lower in prof["name"].lower() or prof["name"].lower() in name_lower:
                return sym
        return None
