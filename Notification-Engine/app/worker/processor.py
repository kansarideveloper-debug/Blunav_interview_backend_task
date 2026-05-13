import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.notification import (
    DeliveryStatus,
    Notification,
    NotificationAttempt,
    NotificationDelivery,
    NotificationStatus,
)
from app.providers.base import NotificationMessage
from app.providers.registry import get_provider
from app.services.messaging import MessageBroker

log = logging.getLogger(__name__)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _backoff_seconds(attempt_number: int) -> float:
    settings = get_settings()
    return settings.base_backoff_seconds * (2 ** max(0, attempt_number - 1))


def _aggregate_notification_status(deliveries: list[NotificationDelivery]) -> NotificationStatus:
    if not deliveries:
        return NotificationStatus.SENT
    if any(d.status == DeliveryStatus.DEAD_LETTER for d in deliveries):
        return NotificationStatus.DEAD_LETTER
    if all(d.status == DeliveryStatus.SENT for d in deliveries):
        return NotificationStatus.SENT
    if any(d.status in (DeliveryStatus.RETRYING, DeliveryStatus.PENDING) for d in deliveries):
        return NotificationStatus.RETRYING
    return NotificationStatus.PROCESSING


async def _load_notification(session: AsyncSession, notification_id: UUID) -> Notification | None:
    result = await session.execute(
        select(Notification)
        .options(
            selectinload(Notification.deliveries).selectinload(NotificationDelivery.attempts),
        )
        .where(Notification.id == notification_id)
    )
    return result.scalar_one_or_none()


async def process_notification_message(
    session: AsyncSession,
    broker: MessageBroker,
    *,
    notification_id: UUID,
    deliver_after: float,
) -> None:
    settings = get_settings()
    now_ts = time.time()
    if deliver_after > now_ts:
        await asyncio.sleep(min(60.0, deliver_after - now_ts))

    n = await _load_notification(session, notification_id)
    if not n:
        log.warning("Notification %s not found", notification_id)
        return

    if all(d.status == DeliveryStatus.SENT for d in n.deliveries):
        return

    n.status = NotificationStatus.PROCESSING
    now = datetime.now(UTC)

    due_deliveries: list[NotificationDelivery] = []
    future_retry_at: datetime | None = None

    for d in n.deliveries:
        if d.status == DeliveryStatus.SENT:
            continue
        if d.status == DeliveryStatus.DEAD_LETTER:
            continue
        if d.next_retry_at:
            nr = _as_utc(d.next_retry_at)
            if nr > now:
                future_retry_at = nr if future_retry_at is None else min(future_retry_at, nr)
                continue
        due_deliveries.append(d)

    if not due_deliveries:
        n.status = _aggregate_notification_status(list(n.deliveries))
        await session.commit()
        if future_retry_at is not None:
            delay = max(0.0, future_retry_at.timestamp() - time.time())
            await broker.publish_notification_job(
                notification_id=n.id,
                priority=n.priority,
                deliver_after=time.time() + min(delay, 300.0),
            )
        return

    for delivery in due_deliveries:
        delivery.status = DeliveryStatus.PROCESSING
        delivery.attempt_count += 1
        attempt_no = delivery.attempt_count

        message = NotificationMessage(
            notification_id=str(n.id),
            user_id=n.user_id,
            event_type=n.event_type,
            channel=delivery.channel,
            payload=n.payload,
        )
        provider = get_provider(delivery.channel)

        err: str | None = None
        response: dict | None = None
        try:
            response = await provider.send(message)
            delivery.status = DeliveryStatus.SENT
            delivery.last_error = None
            delivery.provider_response = response
            session.add(
                NotificationAttempt(
                    delivery_id=delivery.id,
                    attempt_number=attempt_no,
                    success=True,
                    error_message=None,
                    provider_response=response,
                )
            )
        except Exception as exc:  # noqa: BLE001 — provider boundary
            err = f"{type(exc).__name__}: {exc}"
            delivery.last_error = err
            session.add(
                NotificationAttempt(
                    delivery_id=delivery.id,
                    attempt_number=attempt_no,
                    success=False,
                    error_message=err,
                    provider_response=None,
                )
            )
            if attempt_no >= settings.max_delivery_attempts:
                delivery.status = DeliveryStatus.DEAD_LETTER
                await broker.publish_to_dlq(
                    {
                        "notification_id": str(n.id),
                        "delivery_id": str(delivery.id),
                        "channel": delivery.channel.value,
                        "error": err,
                        "attempts": attempt_no,
                    }
                )
            else:
                delivery.status = DeliveryStatus.RETRYING
                delay = _backoff_seconds(attempt_no)
                delivery.next_retry_at = now + timedelta(seconds=delay)

    n.status = _aggregate_notification_status(list(n.deliveries))
    await session.commit()

    needs_retry = any(d.status == DeliveryStatus.RETRYING for d in n.deliveries)
    if needs_retry:
        next_times = [d.next_retry_at for d in n.deliveries if d.next_retry_at]
        deliver_at = time.time()
        if next_times:
            deliver_at = min(_as_utc(dt).timestamp() for dt in next_times)
        await broker.publish_notification_job(
            notification_id=n.id,
            priority=n.priority,
            deliver_after=deliver_at,
        )
