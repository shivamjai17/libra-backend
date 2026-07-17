"""Payment collection, GST, refunds, and receipt-notification trigger."""
from datetime import date

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import TenantContext
from app.models.enums import NotificationChannel, NotificationType, PaymentStatus
from app.models.operations import ActivityLog, Payment
from app.models.tenant import BranchSettings
from app.schemas.payment import PaymentCreate
from app.services import notifications
from app.services.rules import compute_gst
from app.services.sequences import next_invoice_id


async def _gst_rate(db: AsyncSession, ctx: TenantContext) -> float:
    from sqlalchemy import select

    row = (
        await db.execute(select(BranchSettings).where(BranchSettings.branch_id == ctx.branch_id))
    ).scalar_one_or_none()
    return float(row.gst_rate_pct) if row else 18.0


async def collect(db: AsyncSession, ctx: TenantContext, payload: PaymentCreate) -> Payment:
    gst = compute_gst(payload.amount, await _gst_rate(db, ctx))
    payment = Payment(
        id=await next_invoice_id(db, ctx.branch_id),
        library_id=ctx.library_id,
        branch_id=ctx.branch_id,
        student_id=payload.student_id,
        plan_id=payload.plan_id,
        date=date.today(),
        method=payload.method,
        amount=payload.amount,
        gst=gst,
        status=PaymentStatus.paid,
        description=payload.description,
    )
    db.add(payment)

    # Reduce any outstanding dues on the student.
    from app.models.student import Student

    student = await db.get(Student, payload.student_id)
    if student and student.due_amount:
        student.due_amount = max(0, student.due_amount - payload.amount)

    db.add(
        ActivityLog(
            library_id=ctx.library_id,
            branch_id=ctx.branch_id,
            actor=ctx.user.name,
            action="payment.collected",
            subject=student.name if student else payload.student_id,
            detail=f"₹{payload.amount:,} · {payload.method.value}",
        )
    )
    # Generate the receipt PDF first so the SMS can carry its link.
    await db.flush()
    from app.services import receipt_flow

    link = await receipt_flow.generate_for_payment(db, payment)

    # Auto-send receipt notification (SMS, with the receipt link when available).
    await notifications.send_notification(
        db, ctx, payload.student_id, NotificationType.paid,
        channel=NotificationChannel.SMS, amount=payload.amount, link=link,
    )
    await db.flush()
    return payment


async def refund(db: AsyncSession, ctx: TenantContext, payment_id: str) -> Payment:
    payment = await db.get(Payment, payment_id)
    if payment is None or payment.branch_id != ctx.branch_id:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.status == PaymentStatus.refunded:
        raise HTTPException(status_code=409, detail="Already refunded")
    payment.status = PaymentStatus.refunded
    db.add(
        ActivityLog(
            library_id=ctx.library_id,
            branch_id=ctx.branch_id,
            actor=ctx.user.name,
            action="payment.refunded",
            subject=payment.student_id,
            detail=f"₹{payment.amount:,}",
        )
    )
    await db.flush()
    return payment
