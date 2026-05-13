from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import db_session, idempotency_header, message_broker, rate_limit
from app.schemas.events import IngestEventRequest, IngestEventResponse
from app.services.ingestion import ingest_event
from app.services.messaging import MessageBroker

router = APIRouter(dependencies=[Depends(rate_limit)])


@router.post("/events", response_model=IngestEventResponse)
async def create_event(
    body: IngestEventRequest,
    session: AsyncSession = Depends(db_session),
    broker: MessageBroker = Depends(message_broker),
    client_idempotency_key: str | None = Depends(idempotency_header),
) -> IngestEventResponse:
    notification_id, key, deduped = await ingest_event(
        session,
        broker,
        body,
        client_idempotency_key=client_idempotency_key,
    )
    return IngestEventResponse(
        notification_id=notification_id,
        idempotency_key=key,
        deduplicated=deduped,
    )
