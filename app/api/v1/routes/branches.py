"""Branch performance overview across the whole library (multi-branch view)."""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import TenantContext, get_tenant
from app.core.database import get_db
from app.models.enums import PaymentStatus, SeatStatus
from app.models.operations import Payment
from app.models.catalog import Seat
from app.models.student import Student
from app.models.tenant import Branch, BranchSettings, Staff
from app.schemas.common import ORMModel
from pydantic import BaseModel

router = APIRouter(tags=["branches"])


class BranchCreate(BaseModel):
    name: str
    area: str | None = None


class BranchBrief(ORMModel):
    id: str
    name: str
    area: str | None = None


@router.post("/branches", response_model=BranchBrief, status_code=201)
async def create_branch(payload: BranchCreate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    if ctx.user.role.value not in ("Owner", "Manager"):
        from fastapi import HTTPException
        raise HTTPException(403, "Only an owner or manager can add branches")
    branch = Branch(library_id=ctx.library_id, name=payload.name, area=payload.area or "Branch")
    db.add(branch)
    await db.flush()
    db.add(BranchSettings(branch_id=branch.id))
    await db.commit()
    return branch


class BranchStat(ORMModel):
    id: str
    name: str
    area: str | None = None
    students: int
    revenue: int
    seats_total: int
    seats_occupied: int
    staff: int
    is_active: bool


@router.get("/branches/overview", response_model=list[BranchStat])
async def branches_overview(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    branches = (await db.execute(
        select(Branch).where(Branch.library_id == ctx.library_id).order_by(Branch.created_at)
    )).scalars().all()

    out = []
    month_start = date.today().replace(day=1)
    for b in branches:
        students = (await db.execute(
            select(func.count()).select_from(Student).where(Student.branch_id == b.id)
        )).scalar() or 0
        revenue = (await db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.branch_id == b.id,
                Payment.status == PaymentStatus.paid,
                Payment.date >= month_start,
            )
        )).scalar() or 0
        seats_total = (await db.execute(
            select(func.count()).select_from(Seat).where(Seat.branch_id == b.id)
        )).scalar() or 0
        seats_occ = (await db.execute(
            select(func.count()).select_from(Seat).where(
                Seat.branch_id == b.id, Seat.status == SeatStatus.occupied
            )
        )).scalar() or 0
        staff = (await db.execute(
            select(func.count()).select_from(Staff).where(Staff.branch_id == b.id)
        )).scalar() or 0
        out.append(BranchStat(
            id=b.id, name=b.name, area=b.area, students=students, revenue=int(revenue),
            seats_total=seats_total, seats_occupied=seats_occ, staff=staff,
            is_active=(b.id == ctx.branch_id),
        ))
    return out
