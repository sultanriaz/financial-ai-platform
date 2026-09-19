import re
import logging
from typing import Any
from services.company_service import FINANCIAL_TICKER_MAP, company_service

logger = logging.getLogger("entity-extractor")

# Regex to match tickers like $AAPL, (AAPL), NASDAQ: AAPL, NYSE: JPM
TICKER_PATTERN = re.compile(
    r"(?:\$|NASDAQ:\s*|NYSE:\s*|\()([A-Z]{1,5})(?:\)|\b)",
    re.IGNORECASE
)

# Common words that are uppercase but NOT stock tickers
DISALLOWED_TICKERS = {
    "A", "I", "IT", "ON", "AT", "BY", "FOR", "IN", "OF", "TO", "AND", "OR", "US", "USA",
    "THE", "ALL", "NEW", "NOW", "TOP", "BIG", "AI", "CEO", "CFO", "CTO", "IPO", "ETF",
    "FED", "SEC", "GDP", "CPI", "PPI", "PMI", "USD", "EUR", "GBP", "JPY", "WSJ", "CNBC"
}


class EntityExtractor:
    """
    Extracts organizations and companies mentioned in financial news.
    Combines rule-based financial dictionary resolution, ticker pattern matching,
    and spaCy NER if present.
    """

    def __init__(self):
        self._nlp = None
        self._load_spacy()

    def _load_spacy(self):
        try:
            import spacy
            for model_name in ("en_core_web_sm", "en_core_sci_sm"):
                try:
                    self._nlp = spacy.load(model_name)
                    logger.info("Loaded spaCy model: %s", model_name)
                    return
                except Exception:
                    pass
        except ImportError:
            pass
        logger.info("Using lightweight financial dictionary and regex entity extraction.")

    def extract(self, text: str) -> list[dict[str, str]]:
        """
        Extracts organizations from input text.
        Returns:
            [
                {
                    "company_name": "Apple",
                    "ticker": "AAPL"
                }
            ]
        """
        if not text:
            return []

        results: dict[str, str] = {}  # ticker -> company_name

        # 1. Match company names from financial dictionary
        text_lower = text.lower()
        for name_key, (ticker, canonical_name, _) in FINANCIAL_TICKER_MAP.items():
            # Use word boundary check
            pattern = rf"\b{re.escape(name_key)}\b"
            if re.search(pattern, text_lower):
                # Prefer shorter display name if appropriate, e.g. "Apple" instead of "Apple Inc."
                display_name = name_key.capitalize() if len(name_key.split()) == 1 else canonical_name
                results[ticker] = display_name

        # 2. Match explicit ticker patterns ($AAPL, NASDAQ: AAPL, (AAPL))
        for match in TICKER_PATTERN.finditer(text):
            sym = match.group(1).upper()
            if sym not in DISALLOWED_TICKERS and len(sym) >= 2:
                if sym not in results:
                    resolved = company_service.resolve_company(sym)
                    company_name = resolved[1] if resolved else sym
                    results[sym] = company_name

        # 3. Use spaCy NER if available to discover other ORG mentions
        if self._nlp:
            try:
                doc = self._nlp(text[:1500])
                for ent in doc.ents:
                    if ent.label_ in ("ORG", "ENTITY"):
                        ent_text = ent.text.strip()
                        resolved = company_service.resolve_company(ent_text)
                        if resolved:
                            ticker, canonical_name, _ = resolved
                            if ticker not in results:
                                results[ticker] = ent_text.capitalize() if len(ent_text.split()) == 1 else canonical_name
            except Exception as e:
                logger.debug("spaCy entity extraction error: %s", e)

        output = [
            {"company_name": name, "ticker": ticker}
            for ticker, name in sorted(results.items())
        ]
        return output
