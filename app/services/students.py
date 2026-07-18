"""Student onboarding and read-model assembly."""
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import TenantContext
from app.models.catalog import Batch, Plan, Seat
from app.models.enums import NotificationType, PaymentMethod, PaymentStatus, SeatStatus
from app.models.operations import ActivityLog, Payment
from app.models.student import Student
from app.schemas.student import StudentCreate, StudentOut
from app.services import notifications, seats
from app.services.rules import compute_gst, derive_status, membership_end
from app.services.sequences import next_invoice_id, next_student_id


async def load_one(db: AsyncSession, student_id: str, with_subresources: bool = False) -> Student | None:
    """Fetch a student with plan/batch (and optionally docs) eager-loaded.

    Required because accessing relationships lazily under async raises MissingGreenlet.
    """
    opts = [selectinload(Student.plan), selectinload(Student.batch)]
    if with_subresources:
        opts += [selectinload(Student.documents)]
    result = await db.execute(select(Student).options(*opts).where(Student.id == student_id))
    return result.scalar_one_or_none()


def to_out(student: Student) -> StudentOut:
    """Assemble the UI read-model, computing derived status on the fly."""
    return StudentOut(
        id=student.id,
        name=student.name,
        phone=student.phone,
        email=student.email,
        plan_id=student.plan_id,
        batch_id=student.batch_id,
        hall_id=student.hall_id,
        seat_id=student.seat_id,
        due_amount=student.due_amount,
        active=student.active,
        joined_date=student.joined_date,
        membership_start=student.membership_start,
        membership_end=student.membership_end,
        status=derive_status(student.membership_end, student.due_amount),
        plan_name=student.plan.name if student.plan else None,
        batch_name=student.batch.name if student.batch else None,
    )


async def _assert_unique_contact(
    db: AsyncSession, ctx: TenantContext, phone: str | None, email: str | None, exclude_id: str | None = None
) -> None:
    """Enforce one student per phone and per email within the library."""
    from sqlalchemy import func as _func

    if phone:
        stmt = select(Student.id).where(Student.library_id == ctx.library_id, Student.phone == phone)
        if exclude_id:
            stmt = stmt.where(Student.id != exclude_id)
        if (await db.execute(stmt)).first():
            raise HTTPException(status_code=409, detail="A student with this phone number already exists")
    if email:
        stmt = select(Student.id).where(
            Student.library_id == ctx.library_id, _func.lower(Student.email) == email.lower()
        )
        if exclude_id:
            stmt = stmt.where(Student.id != exclude_id)
        if (await db.execute(stmt)).first():
            raise HTTPException(status_code=409, detail="A student with this email already exists")


async def onboard(db: AsyncSession, ctx: TenantContext, payload: StudentCreate) -> Student:
    await _assert_unique_contact(db, ctx, payload.phone, payload.email)

    # Plan and batch are optional (a brand-new institute may not have set any up
    # yet). If provided, they must be valid for this branch.
    plan = None
    if payload.plan_id:
        plan = await db.get(Plan, payload.plan_id)
        if plan is None or plan.branch_id != ctx.branch_id:
            raise HTTPException(status_code=400, detail="Invalid plan")
    batch = None
    if payload.batch_id:
        batch = await db.get(Batch, payload.batch_id)
        if batch is None or batch.branch_id != ctx.branch_id:
            raise HTTPException(status_code=400, detail="Invalid batch")

    period = payload.duration or (plan.period if plan else None)
    start = date.today()
    sid = await next_student_id(db, ctx.branch_id)

    student = Student(
        id=sid,
        library_id=ctx.library_id,
        branch_id=ctx.branch_id,
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        plan_id=plan.id if plan else None,
        batch_id=batch.id if batch else None,
        hall_id=payload.hall_id,
        due_amount=0,
        joined_date=start,
        membership_start=start,
        # No plan/duration -> no fixed end date (membership_end stays null).
        membership_end=membership_end(start, period) if period else None,
    )
    db.add(student)
    await db.flush()

    # Allocate a seat only if a plan includes one.
    if plan and plan.seat_included and payload.hall_id:
        seat_id = payload.seat_id
        if not seat_id:
            free = (
                await db.execute(
                    select(Seat)
                    .where(Seat.hall_id == payload.hall_id, Seat.status == SeatStatus.available)
                    .limit(1)
                )
            ).scalar_one_or_none()
            seat_id = free.id if free else None
        if seat_id:
            await seats.assign(db, ctx, seat_id, student.id)

    # Initial payment at signup (if any).
    invoice = None
    if payload.initial_payment:
        from app.services.payments import _gst_rate

        gst_rate = await _gst_rate(db, ctx)
        gst = compute_gst(payload.initial_payment, gst_rate)
        invoice = Payment(
            id=await next_invoice_id(db, ctx.branch_id),
            library_id=ctx.library_id,
            branch_id=ctx.branch_id,
            student_id=student.id,
            plan_id=plan.id if plan else None,
            date=start,
            method=PaymentMethod.UPI,
            amount=payload.initial_payment,
            gst=gst,
            status=PaymentStatus.paid,
            description=f"{plan.name} signup" if plan else "Signup payment",
        )
        db.add(invoice)

    # Audit + welcome notification (auto-trigger).
    detail = student.name
    if plan or batch:
        parts = [p for p in [plan.name if plan else None, f"{batch.name} batch" if batch else None] if p]
        detail = " · ".join(parts)
    db.add(
        ActivityLog(
            library_id=ctx.library_id,
            branch_id=ctx.branch_id,
            actor=ctx.user.name,
            action="student.created",
            subject=student.name,
            detail=detail,
        )
    )
    await notifications.send_notification(
        db, ctx, student.id, NotificationType.welcome
    )

    # If they paid at signup, produce the invoice PDF and text them the link too.
    if invoice is not None:
        await db.flush()
        from app.models.enums import NotificationChannel
        from app.services import receipt_flow

        link = await receipt_flow.generate_for_payment(db, invoice)
        await notifications.send_notification(
            db, ctx, student.id, NotificationType.paid,
            channel=NotificationChannel.SMS, amount=invoice.amount, link=link,
        )

    await db.flush()
    return await load_one(db, student.id)
