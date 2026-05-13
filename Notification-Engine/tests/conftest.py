import asyncio
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("BROKER_CONNECT_ON_STARTUP", "false")

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.base import Base
from app.db.session import async_session_factory, init_db
from app.dependencies import message_broker, rate_limit
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _init_database() -> None:
    asyncio.run(init_db())


@pytest.fixture(autouse=True)
async def _clean_database() -> None:
    async with async_session_factory() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()
    yield


class StubBroker:
    def __init__(self) -> None:
        self.jobs: list[dict] = []
        self.dlq: list[dict] = []

    async def publish_notification_job(self, **kwargs) -> None:
        self.jobs.append(kwargs)

    async def publish_to_dlq(self, payload: dict) -> None:
        self.dlq.append(payload)

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None


@pytest.fixture
def stub_broker() -> StubBroker:
    return StubBroker()


@pytest.fixture
async def http_client(stub_broker: StubBroker):
    async def _no_rate_limit() -> None:
        return None

    app.dependency_overrides[rate_limit] = _no_rate_limit
    app.dependency_overrides[message_broker] = lambda: stub_broker
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, stub_broker
    app.dependency_overrides.clear()
