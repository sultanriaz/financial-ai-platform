import httpx
from pydantic import BaseModel, Field
from common.config import settings

class Intelligence(BaseModel):
    company: str | None = None
    ticker: str | None = None
    sector: str | None = None
    event: str | None = None
    impact: str = Field(default="Unknown")
    risk_level: str = Field(default="Unknown")
    category: str = Field(default="Market News")

class OllamaExtractor:
    def __init__(self): self.url = f"{settings.ollama_url}/api/generate"
    async def extract(self, title, description):
        prompt = f"Extract financial market intelligence. Return only JSON matching the schema. Use null when unknown.\nTitle: {title}\nDescription: {description}"
        payload = {"model": settings.ollama_model, "prompt": prompt, "format": Intelligence.model_json_schema(), "stream": False, "options": {"temperature": 0, "num_ctx": 2048, "num_predict": 300}}
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(self.url, json=payload); response.raise_for_status(); raw = response.json()["response"]
        return Intelligence.model_validate_json(raw).model_dump()
