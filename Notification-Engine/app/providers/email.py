import logging
import random
from typing import Any

from app.config import get_settings
from app.models.notification import ChannelType
from app.providers.base import NotificationMessage

log = logging.getLogger(__name__)


class EmailProvider:
    channel = ChannelType.EMAIL

    async def send(self, message: NotificationMessage) -> dict[str, Any]:
        settings = get_settings()
        if settings.failure_simulation_rate > 0 and random.random() < settings.failure_simulation_rate:
            raise TimeoutError("SMTP upstream timeout (simulated)")
        log.info("Email sent to user=%s event=%s", message.user_id, message.event_type)
        return {"provider": "email_mock", "message_id": f"em_{message.notification_id[:8]}"}
