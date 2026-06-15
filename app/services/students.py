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
    """Fetch a student with plan/batch (and optionally docs/notes) eager-loaded.

    Required because accessing relationships lazily under async raises MissingGreenlet.
    """
    opts = [selectinload(Student.plan), selectinload(Student.batch)]
    if with_subresources:
        opts += [selectinload(Student.documents), selectinload(Student.notes)]
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
        joined_date=student.joined_date,
        membership_start=student.membership_start,
        membership_end=student.membership_end,
        status=derive_status(student.membership_end, student.due_amount),
        plan_name=student.plan.name if student.plan else None,
        batch_name=student.batch.name if student.batch else None,
    )


async def onboard(db: AsyncSession, ctx: TenantContext, payload: StudentCreate) -> Student:
    plan = await db.get(Plan, payload.plan_id)
    if plan is None or plan.branch_id != ctx.branch_id:
        raise HTTPException(status_code=400, detail="Invalid plan")
    batch = await db.get(Batch, payload.batch_id)
    if batch is None or batch.branch_id != ctx.branch_id:
        raise HTTPException(status_code=400, detail="Invalid batch")

    period = payload.duration or plan.period
    start = date.today()
    sid = await next_student_id(db, ctx.branch_id)

    student = Student(
        id=sid,
        library_id=ctx.library_id,
        branch_id=ctx.branch_id,
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        plan_id=plan.id,
        batch_id=batch.id,
        hall_id=payload.hall_id,
        due_amount=0,
        joined_date=start,
        membership_start=start,
        membership_end=membership_end(start, period),
    )
    db.add(student)
    await db.flush()

    # Allocate a seat if the plan includes one.
    if plan.seat_included and payload.hall_id:
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
    if payload.initial_payment:
        gst_rate = 18.0
        gst = compute_gst(payload.initial_payment, gst_rate)
        inv = Payment(
            id=await next_invoice_id(db, ctx.branch_id),
            library_id=ctx.library_id,
            branch_id=ctx.branch_id,
            student_id=student.id,
            plan_id=plan.id,
            date=start,
            method=PaymentMethod.UPI,
            amount=payload.initial_payment,
            gst=gst,
            status=PaymentStatus.paid,
            description=f"{plan.name} signup",
        )
        db.add(inv)

    # Audit + welcome notification (auto-trigger).
    db.add(
        ActivityLog(
            library_id=ctx.library_id,
            branch_id=ctx.branch_id,
            actor=ctx.user.name,
            action="student.created",
            subject=student.name,
            detail=f"{plan.name} · {batch.name} batch",
        )
    )
    await notifications.send_notification(
        db, ctx, student.id, NotificationType.welcome
    )
    await db.flush()
    return await load_one(db, student.id)
