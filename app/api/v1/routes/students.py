from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import TenantContext, get_tenant
from app.core.database import get_db
from app.models.enums import StudentStatus
from app.models.operations import AttendanceLog, Payment
from app.models.student import Document, Student
from app.schemas.attendance import AttendanceOut
from app.schemas.common import Page
from app.schemas.payment import PaymentOut
from app.schemas.student import (
    DocumentOut, StudentCreate, StudentDetail, StudentOut, StudentUpdate,
)
from app.services import students as svc
from app.services.rules import derive_status

router = APIRouter(prefix="/students", tags=["students"])


@router.get("", response_model=Page[StudentOut])
async def list_students(
    status: StudentStatus | None = None,
    batch_id: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Student).where(Student.branch_id == ctx.branch_id)
    if batch_id:
        stmt = stmt.where(Student.batch_id == batch_id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(func.lower(Student.name).like(like), func.lower(Student.id).like(like), Student.phone.like(like))
        )
    rows = (await db.execute(stmt.order_by(Student.joined_date.desc()))).scalars().all()
    out = [svc.to_out(s) for s in rows]
    # Derived status is computed, so filter post-hoc.
    if status:
        out = [s for s in out if s.status == status]
    total = len(out)
    start = (page - 1) * page_size
    return Page(items=out[start : start + page_size], total=total, page=page, page_size=page_size)


@router.post("", response_model=StudentOut, status_code=201)
async def create_student(payload: StudentCreate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    student = await svc.onboard(db, ctx, payload)
    return svc.to_out(student)


@router.get("/{student_id}", response_model=StudentDetail)
async def get_student(student_id: str, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    student = await svc.load_one(db, student_id, with_subresources=True)
    if student is None or student.branch_id != ctx.branch_id:
        raise HTTPException(404, "Student not found")
    base = svc.to_out(student).model_dump()
    return StudentDetail(**base, documents=student.documents)


@router.patch("/{student_id}", response_model=StudentOut)
async def update_student(student_id: str, payload: StudentUpdate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    student = await svc.load_one(db, student_id)
    if student is None or student.branch_id != ctx.branch_id:
        raise HTTPException(404, "Student not found")
    data = payload.model_dump(exclude_unset=True)
    # Uniqueness: don't allow a phone/email that another student already uses.
    await svc._assert_unique_contact(
        db, ctx, data.get("phone"), data.get("email"), exclude_id=student_id
    )
    for k, v in data.items():
        setattr(student, k, v)
    await db.flush()
    return svc.to_out(await svc.load_one(db, student_id))


class ActiveBody(BaseModel):
    active: bool


@router.patch("/{student_id}/active", response_model=StudentOut)
async def set_student_active(
    student_id: str, payload: ActiveBody,
    ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db),
):
    """Activate / deactivate a student. Deactivating frees their seat."""
    from app.models.catalog import Seat
    from app.models.enums import SeatStatus

    student = await svc.load_one(db, student_id)
    if student is None or student.branch_id != ctx.branch_id:
        raise HTTPException(404, "Student not found")
    student.active = payload.active
    if not payload.active and student.seat_id:
        seat = (await db.execute(select(Seat).where(Seat.id == student.seat_id))).scalar_one_or_none()
        if seat:
            seat.status = SeatStatus.available
            seat.student_id = None
        student.seat_id = None
    await db.flush()
    return svc.to_out(await svc.load_one(db, student_id))


@router.get("/{student_id}/payments", response_model=list[PaymentOut])
async def student_payments(student_id: str, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    student = await svc.load_one(db, student_id)
    if student is None or student.branch_id != ctx.branch_id:
        raise HTTPException(404, "Student not found")
    rows = (
        await db.execute(
            select(Payment)
            .where(Payment.student_id == student_id, Payment.branch_id == ctx.branch_id)
            .order_by(Payment.date.desc())
        )
    ).scalars().all()
    return rows


@router.get("/{student_id}/attendance", response_model=list[AttendanceOut])
async def student_attendance(student_id: str, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    student = await svc.load_one(db, student_id)
    if student is None or student.branch_id != ctx.branch_id:
        raise HTTPException(404, "Student not found")
    rows = (
        await db.execute(
            select(AttendanceLog)
            .where(AttendanceLog.student_id == student_id, AttendanceLog.branch_id == ctx.branch_id)
            .order_by(AttendanceLog.check_in_at.desc())
            .limit(60)
        )
    ).scalars().all()
    return rows


class SeatAssignBody(BaseModel):
    seat_id: str | None = None  # None = release current seat


@router.patch("/{student_id}/seat", response_model=StudentOut)
async def assign_student_seat(
    student_id: str,
    payload: SeatAssignBody,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    from app.models.catalog import Seat
    from app.models.enums import SeatStatus

    student = await svc.load_one(db, student_id)
    if student is None or student.branch_id != ctx.branch_id:
        raise HTTPException(404, "Student not found")

    # Release old seat if any
    if student.seat_id:
        old_seat = (await db.execute(select(Seat).where(Seat.id == student.seat_id))).scalar_one_or_none()
        if old_seat:
            old_seat.status = SeatStatus.available
            old_seat.student_id = None

    if payload.seat_id:
        new_seat = (
            await db.execute(select(Seat).where(Seat.id == payload.seat_id, Seat.branch_id == ctx.branch_id))
        ).scalar_one_or_none()
        if new_seat is None:
            raise HTTPException(404, "Seat not found")
        if new_seat.status not in (SeatStatus.available,):
            raise HTTPException(409, "Seat is not available")
        new_seat.status = SeatStatus.occupied
        new_seat.student_id = student_id
        student.seat_id = payload.seat_id
        student.hall_id = new_seat.hall_id
    else:
        student.seat_id = None

    await db.flush()
    return svc.to_out(await svc.load_one(db, student_id))
