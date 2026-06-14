from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import TenantContext, get_tenant
from app.core.database import get_db
from app.models.catalog import Hall, Seat
from app.schemas.catalog import SeatAssign, SeatOut, SeatStatusUpdate, SeatTransfer
from app.services import seats as svc

router = APIRouter(prefix="/seats", tags=["seats"])


@router.get("", response_model=list[SeatOut])
async def list_seats(
    hall_id: str | None = None,
    floor: str | None = None,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Seat).where(Seat.branch_id == ctx.branch_id)
    if hall_id:
        stmt = stmt.where(Seat.hall_id == hall_id)
    if floor:
        hall_ids = (
            await db.execute(select(Hall.id).where(Hall.branch_id == ctx.branch_id, Hall.floor == floor))
        ).scalars().all()
        stmt = stmt.where(Seat.hall_id.in_(hall_ids))
    return (await db.execute(stmt.order_by(Seat.row, Seat.number))).scalars().all()


@router.post("/{seat_id:path}/assign", response_model=SeatOut)
async def assign_seat(seat_id: str, payload: SeatAssign, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return await svc.assign(db, ctx, seat_id, payload.student_id)


@router.post("/{seat_id:path}/release", response_model=SeatOut)
async def release_seat(seat_id: str, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return await svc.release(db, ctx, seat_id)


@router.post("/{seat_id:path}/transfer", response_model=SeatOut)
async def transfer_seat(seat_id: str, payload: SeatTransfer, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return await svc.transfer(db, ctx, seat_id, payload.to_seat_id)


@router.patch("/{seat_id:path}/status", response_model=SeatOut)
async def update_seat_status(seat_id: str, payload: SeatStatusUpdate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return await svc.set_status(db, ctx, seat_id, payload.status)
