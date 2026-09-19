import asyncio, json, logging
from contextlib import asynccontextmanager
from aiokafka import AIOKafkaConsumer
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from api.routes import router
from api.websocket import manager
from common.config import settings
from database.db import init_db
from prices.poller import run as run_price_poller

logger = logging.getLogger("api")


async def run_broadcaster() -> None:
    backoff = 1
    while True:
        consumer = AIOKafkaConsumer(
            "financial-news-results",
            bootstrap_servers=settings.kafka_url,
            group_id="dashboard-broadcaster",
            auto_offset_reset="latest",
            value_deserializer=lambda v: json.loads(v.decode()),
        )
        try:
            await consumer.start()
            logger.info("Broadcaster: connected to Kafka, streaming to %d client(s)", len(manager.connections))
            backoff = 1
            async for message in consumer:
                await manager.broadcast(message.value)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.warning("Broadcaster error (%s); retry in %ss", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
        finally:
            try:
                await consumer.stop()
            except Exception:
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    broadcaster_task = asyncio.create_task(run_broadcaster())
    poller_task      = asyncio.create_task(run_price_poller())
    logger.info("Lifespan: broadcaster + price poller started")
    yield
    for task in (broadcaster_task, poller_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Financial AI Intelligence API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler — puts CORS headers on 500s so the browser sees the real error
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    origin = request.headers.get("origin")
    headers = {}
    if origin:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
        headers=headers,
    )


app.include_router(router)


@app.websocket("/ws/news-stream")
async def news_stream(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        manager.disconnect(websocket)