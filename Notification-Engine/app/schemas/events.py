import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PriorityName(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ChannelName(str, Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"


class IngestEventRequest(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=128)
    user_id: str = Field(..., min_length=1, max_length=256)
    channels: list[ChannelName] = Field(..., min_length=1)
    priority: PriorityName
    payload: dict[str, Any] = Field(default_factory=dict)


class IngestEventResponse(BaseModel):
    notification_id: uuid.UUID
    idempotency_key: str
    deduplicated: bool = False


class DeliveryAttemptRead(BaseModel):
    attempt_number: int
    success: bool
    error_message: str | None
    provider_response: dict[str, Any] | None
    created_at: datetime


class DeliveryRead(BaseModel):
    id: uuid.UUID
    channel: ChannelName
    status: str
    attempt_count: int
    last_error: str | None
    provider_response: dict[str, Any] | None
    attempts: list[DeliveryAttemptRead]


class NotificationDetailResponse(BaseModel):
    id: uuid.UUID
    idempotency_key: str
    event_type: str
    user_id: str
    priority: str
    status: str
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    deliveries: list[DeliveryRead]
