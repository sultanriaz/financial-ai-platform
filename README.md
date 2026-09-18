# Financial AI Platform
to run == .\Run-All.ps1 -SkipPatch from react-flow__controls

A real-time financial news intelligence dashboard using RSS, Kafka, FinBERT, Ollama, PostgreSQL, FastAPI, and React.

## Start

```bash
cp .env.example .env
docker compose up -d
```

Optional local Ollama:

```bash
docker compose --profile local-ai up -d ollama
docker exec -it finai-ollama ollama pull mistral:latest
```

## Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=$PWD
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

In separate terminals:

```bash
python -m scraper.rss_worker
python -m ai_engine.consumer
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Notes

FinBERT and Ollama are executed sequentially to reduce 4 GB VRAM contention. For production, add authentication, TLS, migrations, metrics, persistent deduplication, retryable DLQ processing, and RSS licensing checks.
