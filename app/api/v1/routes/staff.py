from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import TenantContext, get_tenant
from app.core.database import get_db
from app.core.security import hash_password
from app.models.tenant import Staff
from app.schemas.staff import StaffCreate, StaffOut, StaffUpdate

router = APIRouter(tags=["staff"])


@router.get("/staff", response_model=list[StaffOut])
async def list_staff(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(Staff).where(Staff.library_id == ctx.library_id).order_by(Staff.name)
    )).scalars().all()
    return rows


@router.post("/staff", response_model=StaffOut, status_code=201)
async def create_staff(payload: StaffCreate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    exists = (await db.execute(select(Staff).where(Staff.email == payload.email))).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "A staff member with this email already exists")
    member = Staff(
        library_id=ctx.library_id,
        branch_id=payload.branch_id or ctx.branch_id,
        name=payload.name, email=payload.email, role=payload.role,
        hashed_password=hash_password(payload.password), active=True,
    )
    db.add(member)
    await db.flush()
    return member


@router.patch("/staff/{staff_id}", response_model=StaffOut)
async def update_staff(staff_id: str, payload: StaffUpdate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    member = await db.get(Staff, staff_id)
    if member is None or member.library_id != ctx.library_id:
        raise HTTPException(404, "Staff not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(member, k, v)
    await db.flush()
    return member


@router.delete("/staff/{staff_id}", status_code=204)
async def delete_staff(staff_id: str, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    member = await db.get(Staff, staff_id)
    if member is None or member.library_id != ctx.library_id:
        return
    if member.id == ctx.user.id:
        raise HTTPException(400, "You cannot remove your own account")
    await db.delete(member)
    await db.flush()
