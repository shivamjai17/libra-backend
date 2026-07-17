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
from app.models.tenant import Library
from app.services.sms import send_sms

TEMPLATES: dict[NotificationType, str] = {
    NotificationType.welcome: (
        "Hi {name}, welcome to {org}! Your membership is active and your seat is booked. "
        "Come in anytime to start studying. - Team {org}"
    ),
    NotificationType.due: (
        "Hi {name}, a reminder that your {org} membership fee{amount} is due soon. "
        "Please renew to keep your seat active. - Team {org}"
    ),
    NotificationType.pending: (
        "Hi {name}, your {org} membership fee{amount} is overdue. "
        "Kindly clear it soon to avoid losing your seat. - Team {org}"
    ),
    # Kept short on purpose: SMS bills per 160-char segment.
    NotificationType.paid: (
        "Hi {name}, payment{amount} received at {org}. Thank you! Receipt: {link}"
    ),
}


def render_template(
    ntype: NotificationType, name: str, amount: int | None = None, org: str = "Writtly",
    link: str | None = None,
) -> str:
    amount_str = f" of Rs {amount:,}" if amount else ""
    first = name.split(" ")[0]
    link_str = f"{link} " if link else ""
    body = TEMPLATES[ntype].format(name=first, amount=amount_str, org=org, link=link_str)
    return body.replace("Receipt:  ", "").replace("Receipt: - ", "- ")


async def send_notification(
    db: AsyncSession,
    ctx: TenantContext,
    student_id: str,
    ntype: NotificationType,
    channel: NotificationChannel = NotificationChannel.SMS,
    message: str | None = None,
    amount: int | None = None,
    link: str | None = None,
) -> Notification:
    student = await db.get(Student, student_id)
    name = student.name if student else "Student"
    library = await db.get(Library, ctx.library_id)
    org = library.name if library else "Writtly"
    body = message or render_template(ntype, name, amount, org=org, link=link)

    # Best-effort SMS delivery via Twilio (never blocks the flow).
    sid = send_sms(student.phone if student else None, body)
    status = DeliveryStatus.sent if sid else DeliveryStatus.queued

    notif = Notification(
        library_id=ctx.library_id,
        branch_id=ctx.branch_id,
        student_id=student_id,
        type=ntype,
        channel=channel,
        message=body,
        sent_at=datetime.now(timezone.utc),
        read=False,
        delivery_status=status,
    )
    db.add(notif)
    await db.flush()
    return notif


async def send_overdue_reminders(db: AsyncSession, ctx: TenantContext) -> int:
    """Send an overdue reminder to every student in the branch with outstanding dues.

    Returns the number of reminders sent. Intended for a scheduled job (cron)
    or the "remind all overdue" button.
    """
    students = (await db.execute(
        select(Student).where(Student.branch_id == ctx.branch_id, Student.due_amount > 0)
    )).scalars().all()
    count = 0
    for s in students:
        await send_notification(
            db, ctx, s.id, NotificationType.pending,
            channel=NotificationChannel.SMS, amount=s.due_amount,
        )
        count += 1
    return count


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
