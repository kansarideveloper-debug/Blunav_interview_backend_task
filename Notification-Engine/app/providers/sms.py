import logging
import random
from typing import Any

from app.config import get_settings
from app.models.notification import ChannelType
from app.providers.base import NotificationMessage

log = logging.getLogger(__name__)


class SmsProvider:
    channel = ChannelType.SMS

    async def send(self, message: NotificationMessage) -> dict[str, Any]:
        settings = get_settings()
        if settings.failure_simulation_rate > 0 and random.random() < settings.failure_simulation_rate:
            raise ConnectionError("SMS carrier unavailable (simulated)")
        log.info("SMS sent to user=%s event=%s", message.user_id, message.event_type)
        return {"provider": "sms_mock", "sid": f"SM_{message.notification_id[:8]}"}
