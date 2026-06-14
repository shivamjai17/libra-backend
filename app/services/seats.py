"""Seat lifecycle. A student holds at most one active seat; transfers are atomic."""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import TenantContext
from app.models.catalog import Seat
from app.models.enums import SeatStatus
from app.models.student import Student


async def _get_seat(db: AsyncSession, ctx: TenantContext, seat_id: str) -> Seat:
    seat = await db.get(Seat, seat_id)
    if seat is None or seat.branch_id != ctx.branch_id:
        raise HTTPException(status_code=404, detail="Seat not found")
    return seat


async def assign(db: AsyncSession, ctx: TenantContext, seat_id: str, student_id: str) -> Seat:
    seat = await _get_seat(db, ctx, seat_id)
    if seat.status == SeatStatus.occupied and seat.student_id != student_id:
        raise HTTPException(status_code=409, detail="Seat already occupied")

    # Release any seat the student currently holds (one active seat rule).
    existing = (
        await db.execute(select(Seat).where(Seat.student_id == student_id))
    ).scalars().all()
    for s in existing:
        if s.id != seat_id:
            s.status = SeatStatus.available
            s.student_id = None
            s.occupied_since = None

    seat.status = SeatStatus.occupied
    seat.student_id = student_id
    seat.occupied_since = datetime.now(timezone.utc).strftime("%I:%M %p").lstrip("0")

    student = await db.get(Student, student_id)
    if student:
        student.seat_id = seat.id
        student.hall_id = seat.hall_id
    await db.flush()
    return seat


async def release(db: AsyncSession, ctx: TenantContext, seat_id: str) -> Seat:
    seat = await _get_seat(db, ctx, seat_id)
    if seat.student_id:
        student = await db.get(Student, seat.student_id)
        if student:
            student.seat_id = None
    seat.status = SeatStatus.available
    seat.student_id = None
    seat.occupied_since = None
    await db.flush()
    return seat


async def transfer(db: AsyncSession, ctx: TenantContext, from_seat_id: str, to_seat_id: str) -> Seat:
    src = await _get_seat(db, ctx, from_seat_id)
    if not src.student_id:
        raise HTTPException(status_code=400, detail="Source seat has no occupant")
    student_id = src.student_id
    await release(db, ctx, from_seat_id)
    return await assign(db, ctx, to_seat_id, student_id)


async def set_status(db: AsyncSession, ctx: TenantContext, seat_id: str, status: SeatStatus) -> Seat:
    seat = await _get_seat(db, ctx, seat_id)
    if status in (SeatStatus.available, SeatStatus.maintenance) and seat.student_id:
        raise HTTPException(status_code=409, detail="Release the occupant first")
    seat.status = status
    await db.flush()
    return seat
