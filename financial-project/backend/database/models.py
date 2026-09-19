from datetime import datetime
from uuid import uuid4
from sqlalchemy import (
    BigInteger, DateTime, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.db import Base


class News(Base):
    __tablename__ = "news"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    published_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    analysis: Mapped["Analysis | None"] = relationship(back_populates="news", cascade="all, delete-orphan", uselist=False)
    companies: Mapped[list["Company"]] = relationship(secondary="news_companies", back_populates="news_items", lazy="selectin")


class Analysis(Base):
    __tablename__ = "analysis"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    news_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("news.id", ondelete="CASCADE"), unique=True, nullable=False)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)
    sentiment_label: Mapped[str] = mapped_column(String(30), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255))
    ticker: Mapped[str | None] = mapped_column(String(30))
    sector: Mapped[str | None] = mapped_column(String(100))
    event: Mapped[str | None] = mapped_column(String(100))
    impact: Mapped[str | None] = mapped_column(String(30))
    risk_level: Mapped[str | None] = mapped_column(String(30))
    category: Mapped[str | None] = mapped_column(String(100))
    news: Mapped[News] = relationship(back_populates="analysis")


class Price(Base):
    __tablename__ = "prices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    interval: Mapped[str] = mapped_column(String(10), default="1h", nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    __table_args__ = (
        UniqueConstraint("ticker", "ts", "interval", name="uq_price_ticker_ts_interval"),
    )


class NewsCompany(Base):
    __tablename__ = "news_companies"
    news_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("news.id", ondelete="CASCADE"), primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ticker: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    market_cap: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_change_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    pe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    news_items: Mapped[list["News"]] = relationship(secondary="news_companies", back_populates="companies")