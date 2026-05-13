import pytest


@pytest.mark.asyncio
async def test_ingest_and_deduplicate(http_client):
    client, broker = http_client
    body = {
        "event_type": "ORDER_CREATED",
        "user_id": "USR_1001",
        "channels": ["EMAIL", "SMS"],
        "priority": "HIGH",
        "payload": {"order_id": "ORD_9001", "amount": 4999},
    }
    r1 = await client.post("/v1/events", json=body)
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["deduplicated"] is False
    assert len(broker.jobs) == 1

    r2 = await client.post("/v1/events", json=body)
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["deduplicated"] is True
    assert data2["notification_id"] == data1["notification_id"]
    assert len(broker.jobs) == 1


@pytest.mark.asyncio
async def test_header_idempotency_key(http_client):
    client, broker = http_client
    body = {
        "event_type": "PAYMENT_FAILED",
        "user_id": "u1",
        "channels": ["EMAIL"],
        "priority": "CRITICAL",
        "payload": {},
    }
    headers = {"X-Idempotency-Key": "pay-webhook-123"}
    r1 = await client.post("/v1/events", json=body, headers=headers)
    assert r1.status_code == 200
    r2 = await client.post(
        "/v1/events",
        json={
            **body,
            "payload": {"different": True},
        },
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["deduplicated"] is True
    assert len(broker.jobs) == 1
