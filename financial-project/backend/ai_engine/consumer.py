import asyncio, json, logging
from datetime import datetime
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from sqlalchemy import select
from ai_engine.entity_extractor import EntityExtractor
from ai_engine.llm_processor import OllamaExtractor
from ai_engine.sentiment import FinBERTSentiment
from common.config import settings
from database.db import SessionLocal, init_db
from database.models import News, Analysis
from services.company_service import company_service

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
    entity_extractor = EntityExtractor()

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

                    full_text = f'{article["title"]}. {article.get("description", "")}'

                    # 1. Entity Extraction
                    extracted_entities = entity_extractor.extract(full_text)

                    # 2. FinBERT Sentiment
                    result = sentiment.analyze(full_text)

                    # 3. Ollama for event/impact (optional)
                    try:
                        llm_meta = await extractor.extract(
                            article["title"], article.get("description", "")
                        )
                        result.update(llm_meta)
                    except Exception as exc:
                        logger.warning("Ollama unavailable, using fallbacks: %s", exc)
                        result.update(_OLLAMA_FALLBACK)

                    # If Ollama found a company not in extracted_entities, add it
                    if result.get("company") or result.get("ticker"):
                        sym = result.get("ticker")
                        if sym and not any(e.get("ticker") == sym for e in extracted_entities):
                            extracted_entities.append({
                                "company_name": result.get("company") or sym,
                                "ticker": sym
                            })

                    # 4. Company Enrichment & Database association
                    enriched_companies = await company_service.enrich_news_companies(
                        session, news.id, extracted_entities
                    )

                    primary_company = enriched_companies[0]["name"] if enriched_companies else result.get("company")
                    primary_ticker = enriched_companies[0]["ticker"] if enriched_companies else result.get("ticker")

                    session.add(Analysis(
                        news_id=news.id,
                        sentiment_score=result["score"],
                        sentiment_label=result["sentiment"],
                        company=primary_company,
                        ticker=primary_ticker,
                        sector=result.get("sector"),
                        event=result.get("event"),
                        impact=result.get("impact"),
                        risk_level=result.get("risk_level"),
                        category=result.get("category"),
                    ))
                    await session.commit()

                out_payload = {
                    **article,
                    **result,
                    "company": primary_company,
                    "ticker": primary_ticker,
                    "companies": enriched_companies,
                }
                await producer.send_and_wait("financial-news-results", out_payload)
                await consumer.commit()
                logger.info(
                    "Processed: %s | %s (%.3f) | %d companies",
                    article["title"][:60], result["sentiment"], result["score"], len(enriched_companies)
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