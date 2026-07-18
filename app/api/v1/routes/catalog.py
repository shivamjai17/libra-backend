from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import TenantContext, get_tenant
from app.core.database import get_db
from app.models.catalog import Batch, Hall, Plan, Seat
from app.models.enums import SeatStatus
from app.schemas.catalog import (
    BatchCreate, BatchOut, BatchUpdate,
    HallCreate, HallOut, HallUpdate,
    PlanCreate, PlanOut, PlanUpdate,
)

router = APIRouter(tags=["catalog"])


# ----- Plans -----
@router.get("/plans", response_model=list[PlanOut])
async def list_plans(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(Plan).where(Plan.branch_id == ctx.branch_id, Plan.active.is_(True))
    )).scalars().all()
    return rows


@router.post("/plans", response_model=PlanOut, status_code=201)
async def create_plan(payload: PlanCreate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    plan = Plan(library_id=ctx.library_id, branch_id=ctx.branch_id, **payload.model_dump())
    db.add(plan)
    await db.flush()
    return plan


@router.patch("/plans/{plan_id}", response_model=PlanOut)
async def update_plan(plan_id: str, payload: PlanUpdate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    plan = await db.get(Plan, plan_id)
    if plan is None or plan.branch_id != ctx.branch_id:
        raise HTTPException(404, "Plan not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(plan, k, v)
    await db.flush()
    return plan


@router.delete("/plans/{plan_id}", status_code=204)
async def delete_plan(plan_id: str, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    plan = await db.get(Plan, plan_id)
    if plan and plan.branch_id == ctx.branch_id:
        from app.models.student import Student

        in_use = await db.scalar(
            select(func.count()).select_from(Student).where(Student.plan_id == plan_id)
        )
        if in_use:
            # Students reference this plan — keep the row (for their history)
            # but hide it from the list.
            plan.active = False
        else:
            await db.delete(plan)
        await db.flush()


# ----- Batches -----
@router.get("/batches", response_model=list[BatchOut])
async def list_batches(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(Batch).where(Batch.branch_id == ctx.branch_id))).scalars().all()


@router.post("/batches", response_model=BatchOut, status_code=201)
async def create_batch(payload: BatchCreate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    batch = Batch(library_id=ctx.library_id, branch_id=ctx.branch_id, **payload.model_dump())
    db.add(batch)
    await db.flush()
    return batch


@router.patch("/batches/{batch_id}", response_model=BatchOut)
async def update_batch(batch_id: str, payload: BatchUpdate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    batch = await db.get(Batch, batch_id)
    if batch is None or batch.branch_id != ctx.branch_id:
        raise HTTPException(404, "Batch not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(batch, k, v)
    await db.flush()
    return batch


# ----- Halls (capacity derived) -----
@router.get("/halls", response_model=list[HallOut])
async def list_halls(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(Hall).where(Hall.branch_id == ctx.branch_id))).scalars().all()


@router.post("/halls", response_model=HallOut, status_code=201)
async def create_hall(payload: HallCreate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    hall = Hall(library_id=ctx.library_id, branch_id=ctx.branch_id, **payload.model_dump())
    db.add(hall)
    await db.flush()
    # Materialize the seat grid.
    rows = [chr(ord("A") + r) for r in range(hall.rows)]
    for r in rows:
        for n in range(1, hall.cols + 1):
            code = f"{r}-{n}"
            db.add(Seat(
                id=f"{hall.id}:{code}", code=code, hall_id=hall.id,
                library_id=ctx.library_id, branch_id=ctx.branch_id,
                row=r, number=n, status=SeatStatus.available,
            ))
    await db.flush()
    return hall


@router.delete("/batches/{batch_id}", status_code=204)
async def delete_batch(batch_id: str, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    batch = await db.get(Batch, batch_id)
    if batch and batch.branch_id == ctx.branch_id:
        await db.delete(batch)
        await db.flush()


@router.delete("/halls/{hall_id}", status_code=204)
async def delete_hall(hall_id: str, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    hall = await db.get(Hall, hall_id)
    if hall and hall.branch_id == ctx.branch_id:
        await db.delete(hall)  # seats cascade via relationship
        await db.flush()
