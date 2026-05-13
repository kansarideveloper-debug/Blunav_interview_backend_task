from app.schemas.events import ChannelName
from app.services.idempotency import compute_idempotency_key


def test_idempotency_key_stable() -> None:
    k1 = compute_idempotency_key(
        event_type="ORDER_CREATED",
        user_id="u1",
        channels=[ChannelName.EMAIL, ChannelName.SMS],
        payload={"order_id": "1"},
        client_key=None,
    )
    k2 = compute_idempotency_key(
        event_type="ORDER_CREATED",
        user_id="u1",
        channels=[ChannelName.SMS, ChannelName.EMAIL],
        payload={"order_id": "1"},
        client_key=None,
    )
    assert k1 == k2


def test_client_key_wins() -> None:
    k = compute_idempotency_key(
        event_type="X",
        user_id="u",
        channels=[ChannelName.PUSH],
        payload={},
        client_key="my-key",
    )
    assert k == "my-key"


def test_same_payload_same_key() -> None:
    kw = dict(
        event_type="ORDER_CREATED",
        user_id="u1",
        channels=[ChannelName.EMAIL],
        payload={"a": 1},
        client_key=None,
    )
    assert compute_idempotency_key(**kw) == compute_idempotency_key(**kw)  # type: ignore[arg-type]
