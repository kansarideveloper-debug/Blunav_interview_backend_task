from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import db_session, rate_limit
from app.schemas.events import NotificationDetailResponse
from app.services.notification_query import get_notification_detail, to_detail_response

router = APIRouter(dependencies=[Depends(rate_limit)])


@router.get("/notifications/{notification_id}", response_model=NotificationDetailResponse)
async def read_notification(
    notification_id: UUID,
    session: AsyncSession = Depends(db_session),
) -> NotificationDetailResponse:
    n = await get_notification_detail(session, notification_id)
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    return to_detail_response(n)
