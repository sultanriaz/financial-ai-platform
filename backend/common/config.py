# FIX #7:  ollama_model default now matches .env.example and README pull command.
# FIX #13: cors_origins is a configurable list so CORS is not hardcoded to one origin.
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str         = "postgresql+asyncpg://financial:financial@localhost:5432/financial_ai"
    kafka_url: str            = "localhost:9092"
    ollama_url: str           = "http://localhost:11434"
    ollama_model: str         = "mistral:latest"   # aligned with docs
    rss_interval_seconds: int = 15
    api_host: str             = "0.0.0.0"
    api_port: int             = 8000
    # CORS — override with CORS_ORIGINS='["https://your.domain"]' in .env
    cors_origins: list[str]   = ["http://localhost:5173", "http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
