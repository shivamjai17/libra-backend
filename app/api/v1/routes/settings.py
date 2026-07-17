from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import TenantContext, get_tenant
from app.core.database import get_db
from app.models.tenant import Branch, BranchSettings, Library
from app.schemas.tenant import (
    BranchOut, BranchSettingsOut, BranchSettingsUpdate, LibraryOut, LibraryUpdate,
)

router = APIRouter(tags=["settings"])


@router.get("/libraries/{library_id}/branches", response_model=list[BranchOut])
async def list_branches(library_id: str, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    if library_id != ctx.library_id:
        raise HTTPException(403, "Not your library")
    return (await db.execute(select(Branch).where(Branch.library_id == library_id))).scalars().all()


@router.get("/settings/profile", response_model=LibraryOut)
async def get_profile(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    return await db.get(Library, ctx.library_id)


@router.patch("/settings/profile", response_model=LibraryOut)
async def update_profile(payload: LibraryUpdate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    lib = await db.get(Library, ctx.library_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(lib, k, v)
    await db.flush()
    return lib


@router.get("/settings/payments", response_model=BranchSettingsOut)
async def get_payment_settings(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(select(BranchSettings).where(BranchSettings.branch_id == ctx.branch_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Settings not found")
    return row


@router.patch("/settings/payments", response_model=BranchSettingsOut)
async def update_payment_settings(payload: BranchSettingsUpdate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(select(BranchSettings).where(BranchSettings.branch_id == ctx.branch_id))
    ).scalar_one_or_none()
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    await db.flush()
    return row


@router.post("/settings/logo", response_model=LibraryOut)
async def upload_logo(
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Upload / replace the library logo (PNG, JPG or WEBP, max 2 MB).

    The image is downscaled to 512px and stored; the URL is saved on the
    library and used on receipts.
    """
    from app.services.storage import process_logo

    raw = await file.read()
    url, error = process_logo(raw, file.content_type or "", ctx.library_id)
    if error:
        raise HTTPException(400, error)

    library = await db.get(Library, ctx.library_id)
    if library is None:
        raise HTTPException(404, "Library not found")
    library.logo_url = url
    await db.flush()
    return library
