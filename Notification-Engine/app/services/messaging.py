import json
import logging
from typing import Any
from uuid import UUID

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message

from app.config import get_settings
from app.models.notification import NotificationPriority

log = logging.getLogger(__name__)

_PRIORITY_TO_BROKER: dict[NotificationPriority, int] = {
    NotificationPriority.CRITICAL: 10,
    NotificationPriority.HIGH: 7,
    NotificationPriority.MEDIUM: 4,
    NotificationPriority.LOW: 1,
}


class MessageBroker:
    """RabbitMQ publisher with a durable priority queue."""

    def __init__(self) -> None:
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.RobustChannel | None = None
        self._exchange: aio_pika.Exchange | None = None

    async def connect(self) -> None:
        settings = get_settings()
        self._connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=50)
        assert self._channel is not None
        self._exchange = await self._channel.declare_exchange(
            settings.exchange_name,
            ExchangeType.TOPIC,
            durable=True,
        )
        queue = await self._channel.declare_queue(
            settings.queue_name,
            durable=True,
            arguments={"x-max-priority": 10},
        )
        await queue.bind(self._exchange, routing_key="notify")
        await self._channel.declare_queue(settings.dlq_name, durable=True)
        log.info("RabbitMQ publisher topology ready")

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
        self._connection = None
        self._channel = None
        self._exchange = None

    async def publish_notification_job(
        self,
        *,
        notification_id: UUID,
        priority: NotificationPriority,
        deliver_after: float = 0.0,
    ) -> None:
        if not self._exchange:
            raise RuntimeError("Message broker is not connected")
        body: dict[str, Any] = {
            "notification_id": str(notification_id),
            "deliver_after": deliver_after,
        }
        msg = Message(
            json.dumps(body).encode("utf-8"),
            delivery_mode=DeliveryMode.PERSISTENT,
            priority=_PRIORITY_TO_BROKER[priority],
        )
        await self._exchange.publish(msg, routing_key="notify")

    async def publish_to_dlq(self, payload: dict[str, Any]) -> None:
        settings = get_settings()
        if not self._channel:
            raise RuntimeError("Message broker is not connected")
        await self._channel.default_exchange.publish(
            Message(
                json.dumps(payload).encode("utf-8"),
                delivery_mode=DeliveryMode.PERSISTENT,
            ),
            routing_key=settings.dlq_name,
        )


_broker: MessageBroker | None = None


def get_broker() -> MessageBroker:
    global _broker
    if _broker is None:
        _broker = MessageBroker()
    return _broker
