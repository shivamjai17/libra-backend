"""Notification flow: template rendering, send/queue, mark-read.

Real delivery requires provider integrations (WhatsApp Business API / SMS / SMTP)
plus delivery webhooks to advance `delivery_status`. Here we queue + log.
"""
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import TenantContext
from app.models.enums import DeliveryStatus, NotificationChannel, NotificationType
from app.models.operations import Notification
from app.models.student import Student

TEMPLATES: dict[NotificationType, str] = {
    NotificationType.welcome: (
        "Hi {name}, welcome to {org}! Your membership is now active. "
        "Show this message at the desk to get your seat assigned."
    ),
    NotificationType.due: (
        "Hi {name}, a friendly reminder that your membership fee{amount} is due soon. "
        "Please pay to keep your seat active."
    ),
    NotificationType.pending: (
        "Hi {name}, we haven't received your pending payment{amount}. "
        "Kindly clear it at the earliest to avoid suspension."
    ),
    NotificationType.paid: (
        "Hi {name}, we've received your payment{amount}. Thank you! Your receipt is attached."
    ),
}


def render_template(
    ntype: NotificationType, name: str, amount: int | None = None, org: str = "StudyHub"
) -> str:
    amount_str = f" of ₹{amount:,}" if amount else ""
    first = name.split(" ")[0]
    return TEMPLATES[ntype].format(name=first, amount=amount_str, org=org)


async def send_notification(
    db: AsyncSession,
    ctx: TenantContext,
    student_id: str,
    ntype: NotificationType,
    channel: NotificationChannel = NotificationChannel.WhatsApp,
    message: str | None = None,
    amount: int | None = None,
) -> Notification:
    student = await db.get(Student, student_id)
    name = student.name if student else "Student"
    body = message or render_template(ntype, name, amount)

    notif = Notification(
        library_id=ctx.library_id,
        branch_id=ctx.branch_id,
        student_id=student_id,
        type=ntype,
        channel=channel,
        message=body,
        sent_at=datetime.now(timezone.utc),
        read=False,
        delivery_status=DeliveryStatus.queued,  # advanced by provider webhook in prod
    )
    db.add(notif)
    await db.flush()
    return notif


async def mark_all_read(db: AsyncSession, ctx: TenantContext) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.branch_id == ctx.branch_id, Notification.read.is_(False))
        .values(read=True)
    )


async def unread_count(db: AsyncSession, ctx: TenantContext) -> int:
    return await db.scalar(
        select(__import__("sqlalchemy").func.count())
        .select_from(Notification)
        .where(Notification.branch_id == ctx.branch_id, Notification.read.is_(False))
    ) or 0
