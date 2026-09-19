# FIX #1: article_id now returns a deterministic UUID5 string instead of a
# 64-char SHA-256 hex digest.  Postgres UUID columns (as_uuid=False) expect a
# 32- or 36-char UUID string; the old value always raised DataError and routed
# every article to the DLQ before any AI processing could happen.
import asyncio, logging, uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import aiohttp, feedparser
from bs4 import BeautifulSoup
from common.config import settings
from scraper.producer import NewsProducer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rss-worker")

FEEDS = {
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "CNBC":          "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "MarketWatch":   "https://feeds.marketwatch.com/marketwatch/topstories/",
    "Investing.com": "https://www.investing.com/rss/news_25.rss",
}


def clean_html(value: str) -> str:
    return BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)


def article_id(url: str) -> str:
    """
    Return a deterministic, Postgres-compatible UUID derived from the article URL.
    uuid5(NAMESPACE_URL, url) is stable (same URL → same ID, dedup still works)
    and produces a 36-char UUID-format string that passes Postgres UUID column
    validation. Previously sha256.hexdigest() returned 64 chars → DataError.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, url))


def parse_date(entry) -> str:
    raw = entry.get("published") or entry.get("updated")
    if not raw:
        return datetime.now(timezone.utc).isoformat()
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return datetime.now(timezone.utc).isoformat()


async def fetch_feed(session: aiohttp.ClientSession, source: str, feed_url: str) -> list[dict]:
    for attempt in range(3):
        try:
            async with session.get(
                feed_url,
                timeout=aiohttp.ClientTimeout(total=20),
                headers={"User-Agent": "FinancialAIPlatform/1.0"},
            ) as response:
                response.raise_for_status()
                body = await response.read()
            parsed = feedparser.parse(body)
            articles = []
            for entry in parsed.entries:
                url   = entry.get("link")
                title = clean_html(entry.get("title", ""))
                if not url or not title:
                    continue
                articles.append({
                    "id":             article_id(url),
                    "title":          title[:1000],
                    "description":    clean_html(entry.get("summary", ""))[:5000],
                    "source":         source,
                    "url":            url,
                    "published_time": parse_date(entry),
                    "timestamp":      datetime.now(timezone.utc).isoformat(),
                })
            return articles
        except Exception as exc:
            logger.warning("Feed failure %s attempt %s: %s", source, attempt + 1, exc)
            await asyncio.sleep(2 ** attempt)
    return []


async def run() -> None:
    producer = NewsProducer(settings.kafka_url, "financial-news-raw")
    await producer.start()
    seen: set[str] = set()
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=10)) as session:
            while True:
                batches = await asyncio.gather(
                    *(fetch_feed(session, s, u) for s, u in FEEDS.items()),
                    return_exceptions=True,
                )
                for batch in batches:
                    if isinstance(batch, Exception):
                        continue
                    for article in batch:
                        if article["id"] not in seen:
                            seen.add(article["id"])
                            await producer.send(article)
                if len(seen) > 25_000:
                    seen = set(list(seen)[-10_000:])
                await asyncio.sleep(settings.rss_interval_seconds)
    finally:
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(run())
