from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import TenantContext, get_tenant
from app.core.database import get_db
from app.models.inventory import Asset
from app.schemas.inventory import AssetCreate, AssetOut, AssetUpdate

router = APIRouter(tags=["inventory"])


@router.get("/inventory", response_model=list[AssetOut])
async def list_assets(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(Asset).where(Asset.branch_id == ctx.branch_id).order_by(Asset.category, Asset.name)
    )).scalars().all()
    return rows


@router.post("/inventory", response_model=AssetOut, status_code=201)
async def create_asset(payload: AssetCreate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    asset = Asset(library_id=ctx.library_id, branch_id=ctx.branch_id, **payload.model_dump())
    db.add(asset)
    await db.flush()
    return asset


@router.patch("/inventory/{asset_id}", response_model=AssetOut)
async def update_asset(asset_id: str, payload: AssetUpdate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    asset = await db.get(Asset, asset_id)
    if asset is None or asset.branch_id != ctx.branch_id:
        raise HTTPException(404, "Asset not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(asset, k, v)
    await db.flush()
    return asset


@router.delete("/inventory/{asset_id}", status_code=204)
async def delete_asset(asset_id: str, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    asset = await db.get(Asset, asset_id)
    if asset and asset.branch_id == ctx.branch_id:
        await db.delete(asset)
        await db.flush()
