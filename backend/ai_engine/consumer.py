import asyncio, json, logging
from datetime import datetime
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from sqlalchemy import select
from ai_engine.llm_processor import OllamaExtractor
from ai_engine.sentiment import FinBERTSentiment
from common.config import settings
from database.db import SessionLocal, init_db
from database.models import News, Analysis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-consumer")

# Defaults used when Ollama is unreachable so the article still lands in Postgres.
_OLLAMA_FALLBACK = {
    "company": None, "ticker": None, "sector": None,
    "event": None, "impact": "Unknown",
    "risk_level": "Unknown", "category": "Market News",
}


async def run() -> None:
    await init_db()

    consumer = AIOKafkaConsumer(
        "financial-news-raw",
        bootstrap_servers=settings.kafka_url,
        group_id="financial-ai-workers",
        enable_auto_commit=False,
        # earliest: read backlog on first run when the group has no offset yet.
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode()),
        max_poll_records=1,
    )
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_url,
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    await consumer.start()
    await producer.start()

    sentiment = FinBERTSentiment()
    extractor = OllamaExtractor()

    try:
        async for message in consumer:
            article = message.value
            try:
                async with SessionLocal() as session:
                    if await session.scalar(select(News).where(News.url == article["url"])):
                        await consumer.commit()
                        continue

                    news = News(
                        id=article["id"],
                        title=article["title"],
                        description=article.get("description"),
                        source=article["source"],
                        url=article["url"],
                        published_time=datetime.fromisoformat(article["published_time"]),
                    )
                    session.add(news)
                    await session.flush()

                    result = sentiment.analyze(
                        f'{article["title"]}. {article.get("description", "")}'
                    )

                    # Ollama is optional. If it's down, keep FinBERT results and
                    # fill entity fields with fallbacks so the row still commits.
                    try:
                        result.update(await extractor.extract(
                            article["title"], article.get("description", "")
                        ))
                    except Exception as exc:
                        logger.warning("Ollama unavailable, skipping entities: %s", exc)
                        result.update(_OLLAMA_FALLBACK)

                    session.add(Analysis(
                        news_id=news.id,
                        sentiment_score=result["score"],
                        sentiment_label=result["sentiment"],
                        company=result.get("company"),
                        ticker=result.get("ticker"),
                        sector=result.get("sector"),
                        event=result.get("event"),
                        impact=result.get("impact"),
                        risk_level=result.get("risk_level"),
                        category=result.get("category"),
                    ))
                    await session.commit()

                await producer.send_and_wait("financial-news-results", {**article, **result})
                await consumer.commit()
                logger.info(
                    "Processed: %s | %s (%.3f)",
                    article["title"][:60], result["sentiment"], result["score"]
                )

            except Exception:
                logger.exception("Processing failed for %s", article.get("url", "unknown"))
                await producer.send_and_wait(
                    "financial-news-dlq", {"article": article, "error": "see consumer logs"}
                )
                await consumer.commit()

    finally:
        sentiment.unload()
        await consumer.stop()
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(run())