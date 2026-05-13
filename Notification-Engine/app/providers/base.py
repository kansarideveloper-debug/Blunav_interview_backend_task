from dataclasses import dataclass
from typing import Any, Protocol

from app.models.notification import ChannelType


@dataclass(frozen=True)
class NotificationMessage:
    notification_id: str
    user_id: str
    event_type: str
    channel: ChannelType
    payload: dict[str, Any]


class NotificationProvider(Protocol):
    channel: ChannelType

    async def send(self, message: NotificationMessage) -> dict[str, Any]:
        """Send notification; returns provider response payload on success."""
        ...
