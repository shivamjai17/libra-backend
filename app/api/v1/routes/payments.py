from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import TenantContext, get_tenant
from app.core.database import get_db
from app.models.enums import PaymentMethod, PaymentStatus
from app.models.operations import Payment
from app.schemas.common import Page
from app.schemas.payment import PaymentCreate, PaymentOut
from app.services import payments as svc

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("", response_model=Page[PaymentOut])
async def list_payments(
    status: PaymentStatus | None = None,
    method: PaymentMethod | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Payment).where(Payment.branch_id == ctx.branch_id)
    if status:
        stmt = stmt.where(Payment.status == status)
    if method:
        stmt = stmt.where(Payment.method == method)
    if q:
        stmt = stmt.where(or_(Payment.id.like(f"%{q}%"), Payment.student_id.like(f"%{q}%")))
    rows = (await db.execute(stmt.order_by(Payment.date.desc()))).scalars().all()
    total = len(rows)
    start = (page - 1) * page_size
    return Page(items=rows[start : start + page_size], total=total, page=page, page_size=page_size)


@router.post("", response_model=PaymentOut, status_code=201)
async def collect_payment(payload: PaymentCreate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return await svc.collect(db, ctx, payload)


@router.post("/{payment_id}/refund", response_model=PaymentOut)
async def refund_payment(payment_id: str, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return await svc.refund(db, ctx, payment_id)
