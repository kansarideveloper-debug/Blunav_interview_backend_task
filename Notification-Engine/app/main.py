from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import api_router
from app.config import get_settings
from app.db.session import init_db
from app.logging_config import configure_logging
from app.services.messaging import get_broker
from app.services.rate_limit import close_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    await init_db()
    broker = get_broker()
    if settings.broker_connect_on_startup:
        await broker.connect()
    yield
    if settings.broker_connect_on_startup:
        await broker.close()
    await close_redis()


app = FastAPI(
    title="Notification Engine",
    version="0.1.0",
    lifespan=lifespan,
    description="High-throughput notification ingestion and delivery (interview / portfolio build).",
)

app.include_router(api_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "notification-engine", "docs": "/docs"}
