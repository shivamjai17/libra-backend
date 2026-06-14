from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import TenantContext, get_tenant
from app.core.database import get_db
from app.models.operations import AttendanceLog
from app.schemas.attendance import (
    AttendanceOut, AttendanceSummary, CheckInRequest, CheckOutRequest,
)
from app.services import attendance as svc

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.post("/checkin", response_model=AttendanceOut)
async def checkin(payload: CheckInRequest, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    student_id = payload.student_id or payload.qr_token
    if not student_id:
        raise HTTPException(400, "student_id or qr_token required")
    return await svc.check_in(db, ctx, student_id, payload.method)


@router.post("/checkout", response_model=AttendanceOut)
async def checkout(payload: CheckOutRequest, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return await svc.check_out(db, ctx, payload.student_id)


@router.get("", response_model=list[AttendanceOut])
async def log(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(AttendanceLog)
            .where(AttendanceLog.branch_id == ctx.branch_id)
            .order_by(AttendanceLog.check_in_at.desc())
            .limit(100)
        )
    ).scalars().all()
    return rows


@router.get("/summary", response_model=AttendanceSummary)
async def summary(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return await svc.summary(db, ctx)
