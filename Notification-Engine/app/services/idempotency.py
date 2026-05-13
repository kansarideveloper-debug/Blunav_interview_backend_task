import hashlib
import json
from typing import Any

from app.schemas.events import ChannelName


def compute_idempotency_key(
    *,
    event_type: str,
    user_id: str,
    channels: list[ChannelName],
    payload: dict[str, Any],
    client_key: str | None,
) -> str:
    if client_key:
        key = client_key.strip()
        if len(key) > 512:
            key = key[:512]
        return key
    canonical = json.dumps(
        {
            "event_type": event_type,
            "user_id": user_id,
            "channels": sorted(c.value for c in channels),
            "payload": payload,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
