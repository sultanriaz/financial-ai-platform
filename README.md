# Real-Time Financial AI Intelligence & Sentiment Streaming Platform

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Apache Kafka](https://img.shields.io/badge/Apache_Kafka-231F20?style=for-the-badge&logo=apachekafka&logoColor=white)
![FinBERT](https://img.shields.io/badge/FinBERT-HuggingFace-1E3A8A?style=for-the-badge&logo=transformers&logoColor=white)
![spaCy](https://img.shields.io/badge/spaCy-NER-09A3D5?style=for-the-badge&logo=spacy&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-asyncpg-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![WebSockets](https://img.shields.io/badge/WebSockets-Streaming-010101?style=for-the-badge&logo=socketdotio&logoColor=white)

A distributed, event-driven financial intelligence engine built to consume live market news feeds, extract company entities and tickers, calculate financial sentiment polarity using FinBERT, and stream actionable market signals over WebSockets with sub-second end-to-end latency.

---

## 🏛️ Event Pipeline Architecture

```mermaid
sequenceDiagram
    autonumber
    participant Wire as Market News Wires (CNBC / Yahoo Finance)
    participant Producer as Async Ingestion Producer
    participant Kafka as Apache Kafka Broker
    participant AIWorker as FinBERT / spaCy AI Engine
    participant DB as PostgreSQL (asyncpg)
    participant WSGateway as FastAPI WebSocket Gateway
    participant ClientUI as Web Dashboard (React / TypeScript)

    Wire->>Producer: Raw News Headlines & Body
    Producer->>Kafka: Publish Event to 'news-raw-topic'
    Kafka->>AIWorker: Consume Batch of Unprocessed News
    AIWorker->>AIWorker: Extract Companies via spaCy NER -> Map Tickers
    AIWorker->>AIWorker: Run FinBERT Sentiment Model (Positive / Neutral / Negative)
    AIWorker->>DB: Asynchronously Persist Enriched Record (asyncpg)
    AIWorker->>Kafka: Publish to 'sentiment-enriched-topic'
    Kafka->>WSGateway: Stream Consumer Listeners
    WSGateway->>ClientUI: Real-Time WebSocket Push (< 850ms End-to-End)
```

---

## 🔬 Technical Components

1. **Distributed Event Ingestion:** Asynchronous workers poll major news wires and publish raw ingestion events to Apache Kafka topics.
2. **Entity & Ticker Mapping (spaCy NER):** Extracts corporate entities from noisy headlines and resolves them against stock exchange ticker universes.
3. **FinBERT Tensor Inference:** Utilizes ProsusAI's fine-tuned `FinBERT` transformer to generate domain-accurate financial sentiment classifications and confidence scores.
4. **Asynchronous Persistence & WebSocket Broadcast:** High-throughput async database writes via `asyncpg` paired with persistent FastAPI WebSocket connections streaming signals to frontend subscribers.

---

## 📁 Repository Structure

```
financial-ai-platform/
└── financial-project/
    ├── backend/
    │   ├── ai_engine/         # Kafka consumer, spaCy NER, and FinBERT processor
    │   │   ├── consumer.py    # Main Kafka consumer loop
    │   │   ├── entity_extractor.py # Named Entity Recognition
    │   │   └── sentiment.py   # FinBERT inference module
    │   ├── api/               # FastAPI routes and WebSocket hub
    │   │   ├── main.py        # Gateway server entrypoint
    │   │   ├── routes.py      # REST endpoints for historical analysis
    │   │   └── websocket.py   # Live WebSocket connection manager
    │   └── common/            # Configuration and database pooling
    ├── docker-compose.yml     # Kafka, Zookeeper, and PostgreSQL topology
    └── requirements.txt       # Python dependencies
```

---

## 🚀 Quickstart & Deployment

### 1. Clone & Start Infrastructure
```bash
git clone https://github.com/sultanriaz/financial-ai-platform.git
cd financial-ai-platform/financial-project
docker compose up -d
```

### 2. Set Up Python Virtual Environment
```bash
python -m venv venv
# Linux / macOS:
source venv/bin/activate
# Windows:
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 3. Launch the API & AI Consumer
```bash
# Start the FastAPI WebSocket server:
python backend/api/main.py

# In a separate terminal, launch the AI streaming consumer:
python backend/ai_engine/consumer.py
```
