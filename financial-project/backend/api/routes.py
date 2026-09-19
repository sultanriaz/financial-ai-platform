import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from database.db import get_session
from database.models import News, Analysis, Price, Company
from api.websocket import manager
from services.company_service import company_service

logger = logging.getLogger("routes")
router = APIRouter()


def _normalize_ticker(t: str) -> str:
    return (t or "").strip().upper().replace(".", "-")


def _safe_iso(dt) -> str | None:
    if dt is None:
        return None
    try:
        return dt.isoformat()
    except Exception:
        return None


@router.get("/news")
async def get_news(limit: int = Query(50, ge=1, le=200), session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(
        select(News, Analysis)
        .options(selectinload(News.companies))
        .outerjoin(Analysis, Analysis.news_id == News.id)
        .order_by(desc(News.timestamp))
        .limit(limit)
    )).all()
    return [
        {
            "id": n.id, "title": n.title, "description": n.description,
            "source": n.source, "url": n.url, "timestamp": n.timestamp,
            "sentiment": a.sentiment_label if a else None,
            "score":     a.sentiment_score if a else None,
            "company":   a.company if a else None,
            "ticker":    a.ticker if a else None,
            "sector":    a.sector if a else None,
            "impact":    a.impact if a else None,
            "category":  a.category if a else None,
            "companies": [
                {"id": c.id, "name": c.company_name, "ticker": c.ticker}
                for c in n.companies
            ] if (hasattr(n, "companies") and n.companies) else (
                [{"id": 0, "name": a.company, "ticker": a.ticker}] if (a and a.company and a.ticker) else []
            ),
        }
        for n, a in rows
    ]


@router.get("/sentiment")
async def sentiment_summary(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(
        select(Analysis.sentiment_label, func.count(Analysis.id))
        .group_by(Analysis.sentiment_label)
    )).all()
    return {label: count for label, count in rows}


@router.get("/entities")
async def entities(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(
        select(Analysis.company, Analysis.ticker, func.count(Analysis.id).label("mentions"))
        .where(Analysis.company.is_not(None))
        .group_by(Analysis.company, Analysis.ticker)
        .order_by(desc("mentions"))
        .limit(20)
    )).all()
    return [{"company": c, "ticker": t, "mentions": m} for c, t, m in rows]


@router.get("/prices/{ticker}")
async def get_prices(
    ticker: str,
    days: int = Query(7, ge=1, le=30),
    session: AsyncSession = Depends(get_session),
):
    sym = _normalize_ticker(ticker)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        price_rows = (await session.execute(
            select(Price)
            .where(Price.ticker == sym, Price.ts >= since)
            .order_by(Price.ts)
        )).scalars().all()
    except Exception:
        logger.exception("prices query failed for %s", sym)
        price_rows = []

    try:
        event_rows = (await session.execute(
            select(Analysis, News)
            .join(News, News.id == Analysis.news_id)
            .where(func.upper(Analysis.ticker) == sym, News.timestamp >= since)
            .order_by(News.timestamp)
        )).all()
    except Exception:
        logger.exception("events query failed for %s", sym)
        event_rows = []

    return {
        "ticker": sym,
        "days":   days,
        "prices": [
            {"ts": _safe_iso(p.ts), "open": p.open, "high": p.high,
             "low": p.low, "close": p.close, "volume": p.volume}
            for p in price_rows
        ],
        "events": [
            {"ts": _safe_iso(n.timestamp), "score": a.sentiment_score,
             "sentiment": a.sentiment_label, "title": n.title,
             "url": n.url, "news_id": n.id}
            for a, n in event_rows
        ],
    }


@router.get("/api/company/{ticker}")
@router.get("/company/{ticker}")
async def get_company_profile_endpoint(
    ticker: str,
    session: AsyncSession = Depends(get_session),
):
    sym = _normalize_ticker(ticker)
    # 1. Fetch company profile (handles in-memory cache, DB cache, and market data provider)
    profile = await company_service.get_company_profile(sym, session)

    # 2. Calculate average AI sentiment score for this ticker
    now = datetime.now(timezone.utc)
    since_7d = now - timedelta(days=7)
    avg_score = None
    try:
        avg_score = await session.scalar(
            select(func.avg(Analysis.sentiment_score))
            .join(News, News.id == Analysis.news_id)
            .where(func.upper(Analysis.ticker) == sym, News.timestamp >= since_7d)
        )
    except Exception as e:
        logger.warning("Sentiment score calc failed for %s: %s", sym, e)

    # If no analysis rows yet, default to positive/neutral baseline (0.75) for demo richness
    sentiment_score = round(float(avg_score), 2) if avg_score is not None else 0.75

    # 3. Fetch related news items
    related_news = []
    try:
        related_rows = (await session.execute(
            select(News, Analysis)
            .outerjoin(Analysis, Analysis.news_id == News.id)
            .outerjoin(Company, News.companies)
            .where(
                (func.upper(Analysis.ticker) == sym) | (func.upper(Company.ticker) == sym)
            )
            .distinct()
            .order_by(desc(News.timestamp))
            .limit(8)
        )).all()

        related_news = [
            {
                "id": n.id,
                "title": n.title,
                "url": n.url,
                "source": n.source,
                "sentiment": a.sentiment_label if a else "Neutral",
                "score": a.sentiment_score if a else 0.0,
                "timestamp": _safe_iso(n.timestamp),
            }
            for n, a in related_rows
        ]
    except Exception as e:
        logger.warning("Related news fetch failed for %s: %s", sym, e)

    return {
        "name": profile.get("name") or sym,
        "ticker": sym,
        "price": profile.get("price"),
        "change_percent": profile.get("change_percent"),
        "market_cap": profile.get("market_cap") or "N/A",
        "sector": profile.get("sector") or "Technology",
        "industry": profile.get("industry"),
        "pe_ratio": profile.get("pe_ratio"),
        "sentiment_score": sentiment_score,
        "related_news": related_news,
        "sparkline": profile.get("sparkline", []),
    }


@router.get("/companies/{ticker}/summary")
async def company_summary(
    ticker: str,
    session: AsyncSession = Depends(get_session),
):
    sym = _normalize_ticker(ticker)
    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)
    since_7d  = now - timedelta(days=7)

    # Every sub-query is independently guarded — one failure doesn't kill the response
    try:
        company_name = await session.scalar(
            select(Analysis.company)
            .where(func.upper(Analysis.ticker) == sym, Analysis.company.is_not(None))
            .limit(1)
        )
    except Exception:
        logger.exception("company lookup failed for %s", sym)
        company_name = None

    def _count_and_avg(since):
        return (
            select(func.count(Analysis.id), func.avg(Analysis.sentiment_score))
            .join(News, News.id == Analysis.news_id)
            .where(func.upper(Analysis.ticker) == sym, News.timestamp >= since)
        )

    try:
        c24, a24 = (await session.execute(_count_and_avg(since_24h))).one()
    except Exception:
        logger.exception("24h stats failed for %s", sym)
        c24, a24 = 0, None

    try:
        c7d, a7d = (await session.execute(_count_and_avg(since_7d))).one()
    except Exception:
        logger.exception("7d stats failed for %s", sym)
        c7d, a7d = 0, None

    try:
        spark = (await session.execute(
            select(Price.ts, Price.close)
            .where(Price.ticker == sym, Price.ts >= since_7d)
            .order_by(Price.ts)
        )).all()
    except Exception:
        logger.exception("sparkline failed for %s", sym)
        spark = []

    latest = spark[-1] if spark else None
    change_pct = None
    if len(spark) >= 2:
        prev = next((row for row in reversed(spark[:-1]) if row[1]), None)
        if prev and prev[1]:
            try:
                change_pct = round((spark[-1][1] - prev[1]) / prev[1] * 100, 2)
            except Exception:
                change_pct = None

    return {
        "ticker": sym,
        "company": company_name or sym,
        "mentions_24h": int(c24 or 0),
        "mentions_7d":  int(c7d or 0),
        "avg_score_24h": round(float(a24 or 0), 3),
        "avg_score_7d":  round(float(a7d or 0), 3),
        "latest_price": float(latest[1]) if latest else None,
        "change_pct": change_pct,
        "sparkline": [{"ts": _safe_iso(t), "close": c} for t, c in spark[-40:]],
    }


@router.get("/pipeline-stats")
async def pipeline_stats(session: AsyncSession = Depends(get_session)):
    """Defensive: every sub-query is independently guarded. Returns partial data on failure."""
    now = datetime.now(timezone.utc)
    one_min_ago  = now - timedelta(minutes=1)
    five_min_ago = now - timedelta(minutes=5)
    one_hour_ago = now - timedelta(hours=1)

    async def _scalar(query, default=0):
        try:
            v = await session.scalar(query)
            return v if v is not None else default
        except Exception:
            logger.exception("pipeline-stats sub-query failed")
            return default

    news_total     = await _scalar(select(func.count(News.id)))
    analysis_total = await _scalar(select(func.count(Analysis.id)))
    price_total    = await _scalar(select(func.count(Price.id)))

    news_1m = await _scalar(
        select(func.count(News.id)).where(News.timestamp >= one_min_ago)
    )
    news_5m = await _scalar(
        select(func.count(News.id)).where(News.timestamp >= five_min_ago)
    )
    news_1h = await _scalar(
        select(func.count(News.id)).where(News.timestamp >= one_hour_ago)
    )
    sources = await _scalar(select(func.count(func.distinct(News.source))))
    tickers = await _scalar(
        select(func.count(func.distinct(Analysis.ticker)))
        .where(Analysis.ticker.is_not(None))
    )
    latest = await _scalar(select(func.max(News.timestamp)), default=None)

    # Histogram — the piece most likely to trip on aliasing. Fetch rows, bucket in Python.
    histogram = []
    try:
        rows = (await session.execute(
            select(News.timestamp)
            .where(News.timestamp >= one_hour_ago)
            .order_by(News.timestamp)
        )).scalars().all()
        from collections import Counter
        bucket_counts: Counter = Counter()
        for ts in rows:
            if ts is None:
                continue
            try:
                key = ts.replace(second=0, microsecond=0)
                bucket_counts[key] += 1
            except Exception:
                continue
        histogram = [
            {"minute": k.isoformat(), "count": int(v)}
            for k, v in sorted(bucket_counts.items())
        ]
    except Exception:
        logger.exception("histogram build failed")

    return {
        "now":            now.isoformat(),
        "news_total":     int(news_total),
        "analysis_total": int(analysis_total),
        "price_total":    int(price_total),
        "news_1m":        int(news_1m),
        "news_5m":        int(news_5m),
        "news_1h":        int(news_1h),
        "sources":        int(sources),
        "tickers":        int(tickers),
        "latest_news":    latest.isoformat() if latest is not None and hasattr(latest, "isoformat") else None,
        "ws_clients":     len(manager.connections),
        "histogram":      histogram,
    }


@router.get("/system-status")
async def system_status():
    return {
        "api": "online", "kafka": "configured", "database": "configured",
        "active_workers": 1,
        "gpu": {"available": False, "memory_used_gb": None, "memory_total_gb": None},
        "articles_per_minute": 0,
    }