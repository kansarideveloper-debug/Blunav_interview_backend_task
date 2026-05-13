from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.notification import Notification, NotificationDelivery
from app.schemas.events import (
    ChannelName,
    DeliveryAttemptRead,
    DeliveryRead,
    NotificationDetailResponse,
)


async def get_notification_detail(session: AsyncSession, notification_id: UUID) -> Notification | None:
    result = await session.execute(
        select(Notification)
        .options(
            selectinload(Notification.deliveries).selectinload(NotificationDelivery.attempts),
        )
        .where(Notification.id == notification_id)
    )
    return result.scalar_one_or_none()


def to_detail_response(n: Notification) -> NotificationDetailResponse:
    deliveries: list[DeliveryRead] = []
    for d in n.deliveries:
        attempts = [
            DeliveryAttemptRead(
                attempt_number=a.attempt_number,
                success=a.success,
                error_message=a.error_message,
                provider_response=a.provider_response,
                created_at=a.created_at,
            )
            for a in sorted(d.attempts, key=lambda x: x.attempt_number)
        ]
        deliveries.append(
            DeliveryRead(
                id=d.id,
                channel=ChannelName(d.channel.value),
                status=d.status.value,
                attempt_count=d.attempt_count,
                last_error=d.last_error,
                provider_response=d.provider_response,
                attempts=attempts,
            )
        )
    return NotificationDetailResponse(
        id=n.id,
        idempotency_key=n.idempotency_key,
        event_type=n.event_type,
        user_id=n.user_id,
        priority=n.priority.value,
        status=n.status.value,
        payload=n.payload,
        created_at=n.created_at,
        updated_at=n.updated_at,
        deliveries=deliveries,
    )
