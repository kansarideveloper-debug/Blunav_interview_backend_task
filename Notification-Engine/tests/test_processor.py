import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import async_session_factory
from app.models.notification import (
    ChannelType,
    DeliveryStatus,
    Notification,
    NotificationDelivery,
    NotificationPriority,
    NotificationStatus,
)
from app.providers import registry as registry_mod
from app.worker import processor as processor_mod
from app.worker.processor import _backoff_seconds, process_notification_message


class StubBroker:
    def __init__(self) -> None:
        self.jobs: list[dict] = []
        self.dlq: list[dict] = []

    async def publish_notification_job(self, **kwargs) -> None:
        self.jobs.append(kwargs)

    async def publish_to_dlq(self, payload: dict) -> None:
        self.dlq.append(payload)


def test_backoff_grows(monkeypatch) -> None:
    monkeypatch.setattr(
        processor_mod,
        "get_settings",
        lambda: type(
            "S",
            (),
            {"base_backoff_seconds": 2.0, "max_delivery_attempts": 5, "failure_simulation_rate": 0.0},
        )(),
    )
    assert _backoff_seconds(1) < _backoff_seconds(3)


@pytest.mark.asyncio
async def test_processor_partial_success(monkeypatch):
    monkeypatch.setattr(
        processor_mod,
        "get_settings",
        lambda: type(
            "S",
            (),
            {"base_backoff_seconds": 0.0, "max_delivery_attempts": 5, "failure_simulation_rate": 0.0},
        )(),
    )

    real_get = registry_mod.get_provider
    sms_tries = {"n": 0}

    class FlakySms:
        channel = ChannelType.SMS

        async def send(self, message):
            sms_tries["n"] += 1
            if sms_tries["n"] < 2:
                raise ConnectionError("simulated carrier failure")
            return {"provider": "sms_mock", "sid": "ok"}

    def get_provider(channel: ChannelType):
        if channel == ChannelType.SMS:
            return FlakySms()
        return real_get(channel)

    monkeypatch.setattr(processor_mod, "get_provider", get_provider)

    broker = StubBroker()

    async with async_session_factory() as session:
        n = Notification(
            idempotency_key="k-proc-1",
            event_type="ORDER_CREATED",
            user_id="u1",
            priority=NotificationPriority.HIGH,
            payload={"x": 1},
            status=NotificationStatus.PENDING,
        )
        session.add(n)
        await session.flush()
        session.add(
            NotificationDelivery(
                notification_id=n.id,
                channel=ChannelType.EMAIL,
                status=DeliveryStatus.PENDING,
            )
        )
        session.add(
            NotificationDelivery(
                notification_id=n.id,
                channel=ChannelType.SMS,
                status=DeliveryStatus.PENDING,
            )
        )
        await session.commit()
        nid = n.id

    async with async_session_factory() as session:
        await process_notification_message(
            session,
            broker,  # type: ignore[arg-type]
            notification_id=nid,
            deliver_after=0.0,
        )

    async with async_session_factory() as session:
        await process_notification_message(
            session,
            broker,  # type: ignore[arg-type]
            notification_id=nid,
            deliver_after=0.0,
        )

    async with async_session_factory() as session:
        res = await session.execute(
            select(Notification)
            .options(selectinload(Notification.deliveries))
            .where(Notification.id == nid)
        )
        n2 = res.scalar_one_or_none()
        assert n2 is not None
        by_ch = {d.channel: d for d in n2.deliveries}
        assert by_ch[ChannelType.EMAIL].status == DeliveryStatus.SENT
        assert by_ch[ChannelType.SMS].status == DeliveryStatus.SENT
