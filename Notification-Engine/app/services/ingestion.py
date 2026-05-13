import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import (
    ChannelType,
    DeliveryStatus,
    Notification,
    NotificationDelivery,
    NotificationPriority,
    NotificationStatus,
)
from app.schemas.events import ChannelName, IngestEventRequest
from app.services.idempotency import compute_idempotency_key
from app.services.messaging import MessageBroker

log = logging.getLogger(__name__)


def _map_channel(c: ChannelName) -> ChannelType:
    return ChannelType[c.value]


async def ingest_event(
    session: AsyncSession,
    broker: MessageBroker,
    body: IngestEventRequest,
    *,
    client_idempotency_key: str | None,
) -> tuple[UUID, str, bool]:
    idempotency_key = compute_idempotency_key(
        event_type=body.event_type,
        user_id=body.user_id,
        channels=body.channels,
        payload=body.payload,
        client_key=client_idempotency_key,
    )

    existing = await session.scalar(
        select(Notification).where(Notification.idempotency_key == idempotency_key)
    )
    if existing:
        return existing.id, idempotency_key, True

    notification = Notification(
        idempotency_key=idempotency_key,
        event_type=body.event_type,
        user_id=body.user_id,
        priority=NotificationPriority[body.priority.value],
        payload=body.payload,
        status=NotificationStatus.PENDING,
    )
    session.add(notification)
    await session.flush()

    for ch in body.channels:
        session.add(
            NotificationDelivery(
                notification_id=notification.id,
                channel=_map_channel(ch),
                status=DeliveryStatus.PENDING,
            )
        )

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        dup = await session.scalar(
            select(Notification).where(Notification.idempotency_key == idempotency_key)
        )
        if dup:
            return dup.id, idempotency_key, True
        raise

    await broker.publish_notification_job(
        notification_id=notification.id,
        priority=notification.priority,
    )
    log.info("Enqueued notification %s priority=%s", notification.id, notification.priority.value)
    return notification.id, idempotency_key, False
