import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import SessionLocal
from database.models import Company, NewsCompany
from services.market_data.providers import create_market_data_provider

logger = logging.getLogger("company-service")

# Common financial company name to ticker and canonical name mapping
FINANCIAL_TICKER_MAP: dict[str, tuple[str, str, str]] = {
    # name_lower: (ticker, canonical_name, sector)
    "apple": ("AAPL", "Apple Inc.", "Technology"),
    "apple inc": ("AAPL", "Apple Inc.", "Technology"),
    "microsoft": ("MSFT", "Microsoft Corporation", "Technology"),
    "nvidia": ("NVDA", "NVIDIA Corporation", "Technology"),
    "google": ("GOOGL", "Alphabet Inc.", "Communication Services"),
    "alphabet": ("GOOGL", "Alphabet Inc.", "Communication Services"),
    "amazon": ("AMZN", "Amazon.com, Inc.", "Consumer Cyclical"),
    "meta": ("META", "Meta Platforms, Inc.", "Communication Services"),
    "facebook": ("META", "Meta Platforms, Inc.", "Communication Services"),
    "tesla": ("TSLA", "Tesla, Inc.", "Consumer Cyclical"),
    "jpmorgan": ("JPM", "JPMorgan Chase & Co.", "Financial Services"),
    "jp morgan": ("JPM", "JPMorgan Chase & Co.", "Financial Services"),
    "jpmorgan chase": ("JPM", "JPMorgan Chase & Co.", "Financial Services"),
    "goldman sachs": ("GS", "The Goldman Sachs Group, Inc.", "Financial Services"),
    "morgan stanley": ("MS", "Morgan Stanley", "Financial Services"),
    "berkshire hathaway": ("BRK-B", "Berkshire Hathaway Inc.", "Financial Services"),
    "berkshire": ("BRK-B", "Berkshire Hathaway Inc.", "Financial Services"),
    "jazz pharmaceuticals": ("JAZZ", "Jazz Pharmaceuticals plc", "Healthcare"),
    "jazz pharma": ("JAZZ", "Jazz Pharmaceuticals plc", "Healthcare"),
    "amd": ("AMD", "Advanced Micro Devices, Inc.", "Technology"),
    "intel": ("INTC", "Intel Corporation", "Technology"),
    "moderna": ("MRNA", "Moderna, Inc.", "Healthcare"),
    "pfizer": ("PFE", "Pfizer Inc.", "Healthcare"),
    "robinhood": ("HOOD", "Robinhood Markets, Inc.", "Financial Services"),
    "sandisk": ("WDC", "Western Digital Corporation", "Technology"),
    "western digital": ("WDC", "Western Digital Corporation", "Technology"),
    "broadcom": ("AVGO", "Broadcom Inc.", "Technology"),
    "qualcomm": ("QCOM", "QUALCOMM Incorporated", "Technology"),
    "tsmc": ("TSM", "Taiwan Semiconductor Manufacturing Company", "Technology"),
    "taiwan semiconductor": ("TSM", "Taiwan Semiconductor Manufacturing Company", "Technology"),
    "netflix": ("NFLX", "Netflix, Inc.", "Communication Services"),
    "disney": ("DIS", "The Walt Disney Company", "Communication Services"),
    "walt disney": ("DIS", "The Walt Disney Company", "Communication Services"),
    "coca-cola": ("KO", "The Coca-Cola Company", "Consumer Defensive"),
    "coca cola": ("KO", "The Coca-Cola Company", "Consumer Defensive"),
    "pepsi": ("PEP", "PepsiCo, Inc.", "Consumer Defensive"),
    "pepsico": ("PEP", "PepsiCo, Inc.", "Consumer Defensive"),
    "walmart": ("WMT", "Walmart Inc.", "Consumer Defensive"),
    "exxon": ("XOM", "Exxon Mobil Corporation", "Energy"),
    "exxonmobil": ("XOM", "Exxon Mobil Corporation", "Energy"),
    "chevron": ("CVX", "Chevron Corporation", "Energy"),
    "visa": ("V", "Visa Inc.", "Financial Services"),
    "mastercard": ("MA", "Mastercard Incorporated", "Financial Services"),
    "bank of america": ("BAC", "Bank of America Corporation", "Financial Services"),
    "citigroup": ("C", "Citigroup Inc.", "Financial Services"),
    "wells fargo": ("WFC", "Wells Fargo & Company", "Financial Services"),
}

CACHE_TTL_SECONDS = 180  # 3 minutes in-memory cache
DB_STALE_MINUTES = 15    # Refresh DB if data is older than 15 minutes


class CompanyService:
    """Service responsible for company information, resolution, market data, and caching."""

    def __init__(self):
        self.provider = create_market_data_provider()
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}

    def resolve_company(self, name: str) -> tuple[str, str, str | None] | None:
        """
        Resolves company name -> (ticker, canonical_name, sector).
        """
        cleaned = (name or "").strip().lower()
        if cleaned in FINANCIAL_TICKER_MAP:
            return FINANCIAL_TICKER_MAP[cleaned]

        # Check ticker if name itself is a known ticker
        upper = name.strip().upper()
        for t, n, s in FINANCIAL_TICKER_MAP.values():
            if upper == t:
                return (t, n, s)

        # Partial matching for corporate names
        for key, (t, n, s) in FINANCIAL_TICKER_MAP.items():
            if len(cleaned) >= 4 and (cleaned in key or key in cleaned):
                return (t, n, s)

        return None

    async def get_company_profile(self, ticker: str, session: AsyncSession | None = None) -> dict[str, Any]:
        """
        Fetch company profile, resolving through cache -> DB -> live provider.
        Exposes:
        {
          "name": "Apple Inc",
          "ticker": "AAPL",
          "price": 227.50,
          "change_percent": 1.8,
          "market_cap": "3.4T",
          "sector": "Technology",
          "pe_ratio": 36.5
        }
        """
        sym = (ticker or "").strip().upper().replace(".", "-")

        # 1. In-memory cache hit
        cached = self._cache.get(sym)
        if cached and (time.time() - cached[0]) < CACHE_TTL_SECONDS:
            return cached[1]

        # 2. Database check
        owns_session = False
        if session is None:
            session = SessionLocal()
            owns_session = True

        try:
            db_company = await session.scalar(
                select(Company).where(func.upper(Company.ticker) == sym).limit(1)
            )

            now_utc = datetime.now(timezone.utc)
            is_stale = True
            if db_company and db_company.last_updated:
                age = now_utc - db_company.last_updated
                if age < timedelta(minutes=DB_STALE_MINUTES) and db_company.current_price is not None:
                    is_stale = False

            # If not stale and has price, return from DB
            if db_company and not is_stale and db_company.current_price is not None:
                profile = {
                    "id": db_company.id,
                    "name": db_company.company_name,
                    "ticker": db_company.ticker,
                    "price": db_company.current_price,
                    "change_percent": db_company.daily_change_percent or 0.0,
                    "market_cap": db_company.market_cap or "N/A",
                    "sector": db_company.sector or "Technology",
                    "industry": db_company.industry,
                    "pe_ratio": db_company.pe_ratio,
                    "exchange": db_company.exchange,
                    "logo_url": db_company.logo_url,
                }
                self._cache[sym] = (time.time(), profile)
                return profile

            # 3. Fetch from market data provider
            live_data = await self.provider.get_profile(sym)
            if not live_data:
                # If provider returns nothing, fallback to existing DB row or minimal mock
                if db_company:
                    profile = {
                        "id": db_company.id,
                        "name": db_company.company_name,
                        "ticker": db_company.ticker,
                        "price": db_company.current_price or 100.0,
                        "change_percent": db_company.daily_change_percent or 0.0,
                        "market_cap": db_company.market_cap or "N/A",
                        "sector": db_company.sector or "Technology",
                        "industry": db_company.industry,
                        "pe_ratio": db_company.pe_ratio,
                        "exchange": db_company.exchange,
                        "logo_url": db_company.logo_url,
                    }
                    return profile
                live_data = {
                    "name": f"{sym} Corporation",
                    "ticker": sym,
                    "price": 100.0,
                    "change_percent": 0.0,
                    "market_cap": "N/A",
                    "sector": "Technology",
                    "industry": None,
                    "pe_ratio": None,
                    "exchange": "NASDAQ",
                    "sparkline": [],
                }

            # 4. Upsert into database
            if db_company:
                db_company.company_name = live_data.get("name") or db_company.company_name
                db_company.current_price = live_data.get("price")
                db_company.daily_change_percent = live_data.get("change_percent")
                db_company.market_cap = live_data.get("market_cap")
                db_company.sector = live_data.get("sector") or db_company.sector
                db_company.industry = live_data.get("industry") or db_company.industry
                db_company.pe_ratio = live_data.get("pe_ratio")
                db_company.exchange = live_data.get("exchange") or db_company.exchange
                db_company.last_updated = now_utc
            else:
                db_company = Company(
                    company_name=live_data.get("name", sym),
                    ticker=sym,
                    current_price=live_data.get("price"),
                    daily_change_percent=live_data.get("change_percent"),
                    market_cap=live_data.get("market_cap"),
                    sector=live_data.get("sector"),
                    industry=live_data.get("industry"),
                    pe_ratio=live_data.get("pe_ratio"),
                    exchange=live_data.get("exchange"),
                    last_updated=now_utc,
                )
                session.add(db_company)

            await session.commit()
            await session.refresh(db_company)

            profile = {
                "id": db_company.id,
                "name": db_company.company_name,
                "ticker": db_company.ticker,
                "price": db_company.current_price,
                "change_percent": db_company.daily_change_percent,
                "market_cap": db_company.market_cap,
                "sector": db_company.sector,
                "industry": db_company.industry,
                "pe_ratio": db_company.pe_ratio,
                "exchange": db_company.exchange,
                "logo_url": db_company.logo_url,
                "sparkline": live_data.get("sparkline", []),
            }

            self._cache[sym] = (time.time(), profile)
            return profile

        except Exception as exc:
            logger.exception("Failed getting company profile for %s: %s", sym, exc)
            return {
                "name": sym,
                "ticker": sym,
                "price": 100.0,
                "change_percent": 0.0,
                "market_cap": "N/A",
                "sector": "Unknown",
                "pe_ratio": None,
                "sparkline": [],
            }
        finally:
            if owns_session:
                await session.close()

    async def enrich_news_companies(
        self,
        session: AsyncSession,
        news_id: str,
        extracted_entities: list[dict[str, str]]
    ) -> list[dict[str, Any]]:
        """
        Associates extracted companies with a news item, saving/updating
        Company records and NewsCompany links in PostgreSQL.
        Returns list of company dicts: [{"id": c.id, "name": c.company_name, "ticker": c.ticker}, ...]
        """
        enriched: list[dict[str, Any]] = []
        if not extracted_entities:
            return enriched

        for ent in extracted_entities:
            ticker = (ent.get("ticker") or "").strip().upper().replace(".", "-")
            name = (ent.get("company_name") or ent.get("name") or ticker).strip()
            if not ticker:
                continue

            try:
                # Find or create company
                company = await session.scalar(
                    select(Company).where(func.upper(Company.ticker) == ticker).limit(1)
                )
                if not company:
                    company = Company(
                        company_name=name,
                        ticker=ticker,
                        sector=ent.get("sector"),
                        last_updated=datetime.now(timezone.utc),
                    )
                    session.add(company)
                    await session.flush()

                # Link to news_companies if not already linked
                existing_link = await session.scalar(
                    select(NewsCompany).where(
                        NewsCompany.news_id == news_id,
                        NewsCompany.company_id == company.id
                    ).limit(1)
                )
                if not existing_link:
                    session.add(NewsCompany(news_id=news_id, company_id=company.id))

                enriched.append({
                    "id": company.id,
                    "name": company.company_name,
                    "ticker": company.ticker,
                })
            except Exception as e:
                logger.warning("Error linking company %s to news %s: %s", ticker, news_id, e)

        return enriched


company_service = CompanyService()
