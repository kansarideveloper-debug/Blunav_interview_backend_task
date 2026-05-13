import asyncio
import json
import logging

import aio_pika
from aio_pika import ExchangeType

from app.config import get_settings
from app.db.session import async_session_factory
from app.logging_config import configure_logging
from app.services.messaging import MessageBroker, get_broker
from app.worker.processor import process_notification_message

log = logging.getLogger(__name__)


async def _declare_topology(channel: aio_pika.Channel) -> aio_pika.Queue:
    settings = get_settings()
    exchange = await channel.declare_exchange(
        settings.exchange_name,
        ExchangeType.TOPIC,
        durable=True,
    )
    queue = await channel.declare_queue(
        settings.queue_name,
        durable=True,
        arguments={"x-max-priority": 10},
    )
    await queue.bind(exchange, routing_key="notify")
    await channel.declare_queue(settings.dlq_name, durable=True)
    return queue


async def run_worker() -> None:
    configure_logging()
    settings = get_settings()
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=20)
    queue = await _declare_topology(channel)
    broker = get_broker()
    await broker.connect()
    log.info("Worker consuming from %s", settings.queue_name)

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                try:
                    payload = json.loads(message.body.decode("utf-8"))
                    from uuid import UUID

                    nid = UUID(payload["notification_id"])
                    deliver_after = float(payload.get("deliver_after") or 0)
                    async with async_session_factory() as session:
                        await process_notification_message(
                            session,
                            broker,
                            notification_id=nid,
                            deliver_after=deliver_after,
                        )
                except Exception:
                    log.exception("Failed processing message")
                    raise


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
