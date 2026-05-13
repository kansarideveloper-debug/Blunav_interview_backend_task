import logging
import random
from typing import Any

from app.config import get_settings
from app.models.notification import ChannelType
from app.providers.base import NotificationMessage

log = logging.getLogger(__name__)


class PushProvider:
    channel = ChannelType.PUSH

    async def send(self, message: NotificationMessage) -> dict[str, Any]:
        settings = get_settings()
        if settings.failure_simulation_rate > 0 and random.random() < settings.failure_simulation_rate:
            raise RuntimeError("Push rate limit exceeded (simulated)")
        log.info("Push sent to user=%s event=%s", message.user_id, message.event_type)
        return {"provider": "push_mock", "delivery_id": f"pv_{message.notification_id[:8]}"}
