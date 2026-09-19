"""
Database migration: creates 'companies' and 'news_companies' tables if not already present,
and backfills existing entities from the 'analysis' table.
"""
import asyncio
import logging
from sqlalchemy import text
from database.db import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("db-migrate")

CREATE_COMPANIES_SQL = """
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    ticker VARCHAR(30) UNIQUE NOT NULL,
    exchange VARCHAR(50),
    sector VARCHAR(100),
    industry VARCHAR(100),
    market_cap VARCHAR(50),
    current_price DOUBLE PRECISION,
    daily_change_percent DOUBLE PRECISION,
    pe_ratio DOUBLE PRECISION,
    logo_url TEXT,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_companies_ticker ON companies(ticker);
"""

CREATE_NEWS_COMPANIES_SQL = """
CREATE TABLE news_companies (
    news_id UUID NOT NULL REFERENCES news(id) ON DELETE CASCADE,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    PRIMARY KEY (news_id, company_id)
);
CREATE INDEX IF NOT EXISTS ix_news_companies_news_id ON news_companies(news_id);
CREATE INDEX IF NOT EXISTS ix_news_companies_company_id ON news_companies(company_id);
"""

BACKFILL_COMPANIES_SQL = """
INSERT INTO companies (company_name, ticker, sector, last_updated)
SELECT DISTINCT ON (UPPER(TRIM(ticker)))
    COALESCE(NULLIF(TRIM(company), ''), UPPER(TRIM(ticker))) AS company_name,
    UPPER(TRIM(ticker)) AS ticker,
    sector,
    NOW()
FROM analysis
WHERE ticker IS NOT NULL AND TRIM(ticker) != ''
ON CONFLICT (ticker) DO UPDATE 
SET company_name = EXCLUDED.company_name,
    sector = COALESCE(companies.sector, EXCLUDED.sector);
"""

BACKFILL_NEWS_COMPANIES_SQL = """
INSERT INTO news_companies (news_id, company_id)
SELECT DISTINCT a.news_id, c.id
FROM analysis a
JOIN companies c ON UPPER(TRIM(a.ticker)) = c.ticker
WHERE a.news_id IS NOT NULL AND a.ticker IS NOT NULL AND TRIM(a.ticker) != ''
ON CONFLICT DO NOTHING;
"""


async def run_migration() -> None:
    logger.info("Starting database migration...")
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
        existing_tables = {row[0] for row in res.fetchall()}

        if "companies" not in existing_tables:
            logger.info("Creating 'companies' table...")
            for stmt in CREATE_COMPANIES_SQL.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    await conn.execute(text(stmt))
        else:
            logger.info("'companies' table already exists.")

        if "news_companies" not in existing_tables:
            logger.info("Creating 'news_companies' table...")
            for stmt in CREATE_NEWS_COMPANIES_SQL.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    await conn.execute(text(stmt))
        else:
            logger.info("'news_companies' table already exists.")

        logger.info("Backfilling companies from analysis...")
        await conn.execute(text(BACKFILL_COMPANIES_SQL))

        logger.info("Backfilling news_companies links...")
        await conn.execute(text(BACKFILL_NEWS_COMPANIES_SQL))

    logger.info("Migration completed successfully.")


if __name__ == "__main__":
    asyncio.run(run_migration())
