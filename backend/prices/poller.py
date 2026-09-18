"""Price poller — every 5 minutes, fetch OHLC for every ticker seen in analysis."""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.db import SessionLocal, init_db
from database.models import Analysis, Price

logger = logging.getLogger("price-poller")

POLL_INTERVAL_SECONDS = 300
LOOKBACK_DAYS = 7
MAX_TICKERS_PER_CYCLE = 50


def _normalize_ticker(t: str) -> str:
    """yfinance uses BRK-B, not BRK.B. Ollama may return either."""
    return (t or "").strip().upper().replace(".", "-")


async def _get_tracked_tickers() -> list[str]:
    async with SessionLocal() as session:
        rows = (await session.execute(
            select(Analysis.ticker)
            .where(Analysis.ticker.is_not(None))
            .distinct()
            .limit(MAX_TICKERS_PER_CYCLE)
        )).scalars().all()
    return sorted({_normalize_ticker(t) for t in rows if t})


def _fetch_history_blocking(ticker: str, days: int) -> list[dict]:
    """Runs in a worker thread — yfinance is synchronous HTTP."""
    import yfinance as yf
    import pandas as pd

    t = yf.Ticker(ticker)
    hist = t.history(period=f"{days}d", interval="1h", auto_adjust=False)
    if hist is None or hist.empty:
        return []

    rows = []
    for idx, row in hist.iterrows():
        try:
            ts = idx.to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            ts = ts.astimezone(timezone.utc)
        except Exception:
            continue

        volume = None
        try:
            v = row["Volume"]
            if v is not None and not pd.isna(v):
                volume = int(v)
        except Exception:
            pass

        rows.append({
            "ts":     ts,
            "open":   float(row["Open"]),
            "high":   float(row["High"]),
            "low":    float(row["Low"]),
            "close":  float(row["Close"]),
            "volume": volume,
        })
    return rows


async def _upsert_prices(ticker: str, rows: list[dict]) -> int:
    if not rows:
        return 0
    written = 0
    async with SessionLocal() as session:
        for r in rows:
            stmt = (
                pg_insert(Price)
                .values(ticker=ticker, interval="1h", **r)
                .on_conflict_do_nothing(constraint="uq_price_ticker_ts_interval")
            )
            result = await session.execute(stmt)
            written += result.rowcount or 0
        await session.commit()
    return written


async def run() -> None:
    await init_db()
    logger.info("Price poller started (interval=%ss)", POLL_INTERVAL_SECONDS)

    while True:
        cycle_start = datetime.now(timezone.utc)
        try:
            tickers = await _get_tracked_tickers()
            logger.info("Price cycle: %d ticker(s) to fetch", len(tickers))

            for ticker in tickers:
                try:
                    rows = await asyncio.to_thread(_fetch_history_blocking, ticker, LOOKBACK_DAYS)
                    written = await _upsert_prices(ticker, rows)
                    logger.info("  %-6s %3d candles, %2d new", ticker, len(rows), written)
                except Exception as exc:
                    logger.warning("  %-6s fetch failed: %s", ticker, exc)
                await asyncio.sleep(1)  # gentle rate limiting
        except Exception:
            logger.exception("Price cycle crashed")

        elapsed = (datetime.now(timezone.utc) - cycle_start).total_seconds()
        sleep_for = max(30.0, POLL_INTERVAL_SECONDS - elapsed)
        await asyncio.sleep(sleep_for)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(run())