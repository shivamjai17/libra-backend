from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import TenantContext, get_tenant
from app.core.database import get_db
from app.schemas.dashboard import AnalyticsOut, DashboardOut, DashboardWidgets, Kpis
from app.services import dashboard as svc

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(
    start_date: date | None = None,
    end_date: date | None = None,
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db)
):
    return DashboardOut(
        kpis=Kpis(**await svc.kpis(db, ctx, start_date, end_date)),
        widgets=DashboardWidgets(**await svc.widgets(db, ctx, start_date, end_date)),
        revenue_trend=await svc.revenue_trend(db, ctx, start_date, end_date),
    )


@router.get("/analytics", response_model=AnalyticsOut)
async def analytics(range: str = "last_12_months", ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return AnalyticsOut(**await svc.analytics(db, ctx))
