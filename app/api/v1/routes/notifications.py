from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import TenantContext, get_tenant
from app.core.database import get_db
from app.models.operations import Notification
from app.schemas.notification import NotificationCreate, NotificationOut, UnreadCount
from app.services import notifications as svc

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread: bool | None = None,
    page: int = Query(1, ge=1),
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Notification).where(Notification.branch_id == ctx.branch_id)
    if unread is not None:
        stmt = stmt.where(Notification.read.is_(not unread))
    return (await db.execute(stmt.order_by(Notification.sent_at.desc()).limit(50))).scalars().all()


@router.get("/unread-count", response_model=UnreadCount)
async def unread(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return UnreadCount(unread=await svc.unread_count(db, ctx))


@router.post("", response_model=NotificationOut, status_code=201)
async def send(payload: NotificationCreate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return await svc.send_notification(
        db, ctx, payload.student_id, payload.type, payload.channel, payload.message
    )


@router.post("/reminders/overdue")
async def send_overdue_reminders(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    """Send an SMS reminder to every student in this branch with outstanding dues.

    Use from the 'Remind all overdue' button, or call on a schedule (cron) for
    fully automatic reminders.
    """
    sent = await svc.send_overdue_reminders(db, ctx)
    return {"sent": sent}


@router.post("/test-sms")
async def test_sms(
    payload: dict,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Diagnostic: send a test SMS and return the exact Twilio result/error.

    Body: {"phone": "9000011111", "message": "optional"}.
    Use this to see WHY sending isn't working (not configured, trial-account
    unverified number, DLT rejection, etc.).
    """
    from app.services.sms import send_sms_result

    phone = (payload or {}).get("phone")
    body = (payload or {}).get("message") or "Test SMS from Writtly. If you received this, SMS is working!"
    return send_sms_result(phone, body)


@router.patch("/read-all", status_code=204)
async def read_all(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    await svc.mark_all_read(db, ctx)
