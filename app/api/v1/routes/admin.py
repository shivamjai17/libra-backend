"""Platform admin console: approve / manage libraries (SaaS operator only)."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, decode_token, verify_password
from app.models.admin import PlatformAdmin
from app.models.enums import LibraryStatus
from app.models.student import Student
from app.models.tenant import Branch, Library, Staff
from app.schemas.auth import AdminLoginRequest, AdminUser
from app.schemas.common import ORMModel

router = APIRouter(prefix="/admin", tags=["admin"])
admin_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/admin/login", auto_error=False)


async def get_admin(token: str | None = Depends(admin_scheme), db: AsyncSession = Depends(get_db)) -> PlatformAdmin:
    exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin auth required",
                        headers={"WWW-Authenticate": "Bearer"})
    if not token:
        raise exc
    try:
        payload = decode_token(token)
        if payload.get("scope") != "platform_admin":
            raise exc
        admin = await db.get(PlatformAdmin, payload.get("sub"))
    except ValueError as e:
        raise exc from e
    if admin is None or not admin.active:
        raise exc
    return admin


class AdminTokenOut(ORMModel):
    access_token: str
    token_type: str = "bearer"
    admin: AdminUser


class LibraryRow(ORMModel):
    id: str
    name: str
    owner_name: str | None = None
    email: str | None = None
    contact_phone: str | None = None
    address: str | None = None
    plan: str
    status: str
    branches: int
    students: int
    staff: int
    created_at: str


@router.post("/login", response_model=AdminTokenOut)
async def admin_login(payload: AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    admin = (await db.execute(select(PlatformAdmin).where(PlatformAdmin.email == payload.email))).scalar_one_or_none()
    if admin is None or not verify_password(payload.password, admin.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect admin email or password")
    token = create_access_token(admin.id, scope="platform_admin")
    return AdminTokenOut(access_token=token, admin=AdminUser(id=admin.id, name=admin.name, email=admin.email))


@router.get("/me", response_model=AdminUser)
async def admin_me(admin: PlatformAdmin = Depends(get_admin)):
    return AdminUser(id=admin.id, name=admin.name, email=admin.email)


@router.get("/libraries", response_model=list[LibraryRow])
async def list_libraries(admin: PlatformAdmin = Depends(get_admin), db: AsyncSession = Depends(get_db)):
    libs = (await db.execute(select(Library).order_by(Library.created_at.desc()))).scalars().all()
    out = []
    for lib in libs:
        branches = (await db.execute(select(func.count()).select_from(Branch).where(Branch.library_id == lib.id))).scalar() or 0
        students = (await db.execute(select(func.count()).select_from(Student).where(Student.library_id == lib.id))).scalar() or 0
        staff = (await db.execute(select(func.count()).select_from(Staff).where(Staff.library_id == lib.id))).scalar() or 0
        out.append(LibraryRow(
            id=lib.id, name=lib.name, owner_name=lib.owner_name, email=lib.email,
            contact_phone=lib.contact_phone, address=lib.address, plan=lib.plan,
            status=lib.status.value, branches=branches, students=students, staff=staff,
            created_at=lib.created_at.isoformat() if lib.created_at else "",
        ))
    return out


async def _set_status(library_id: str, new: LibraryStatus, db: AsyncSession) -> LibraryRow:
    lib = await db.get(Library, library_id)
    if lib is None:
        raise HTTPException(404, "Library not found")
    lib.status = new
    await db.flush()
    branches = (await db.execute(select(func.count()).select_from(Branch).where(Branch.library_id == lib.id))).scalar() or 0
    students = (await db.execute(select(func.count()).select_from(Student).where(Student.library_id == lib.id))).scalar() or 0
    staff = (await db.execute(select(func.count()).select_from(Staff).where(Staff.library_id == lib.id))).scalar() or 0
    await db.commit()
    return LibraryRow(
        id=lib.id, name=lib.name, owner_name=lib.owner_name, email=lib.email,
        contact_phone=lib.contact_phone, address=lib.address, plan=lib.plan,
        status=lib.status.value, branches=branches, students=students, staff=staff,
        created_at=lib.created_at.isoformat() if lib.created_at else "",
    )


@router.post("/libraries/{library_id}/approve", response_model=LibraryRow)
async def approve_library(library_id: str, admin: PlatformAdmin = Depends(get_admin), db: AsyncSession = Depends(get_db)):
    return await _set_status(library_id, LibraryStatus.approved, db)


@router.post("/libraries/{library_id}/reject", response_model=LibraryRow)
async def reject_library(library_id: str, admin: PlatformAdmin = Depends(get_admin), db: AsyncSession = Depends(get_db)):
    return await _set_status(library_id, LibraryStatus.rejected, db)


@router.post("/libraries/{library_id}/suspend", response_model=LibraryRow)
async def suspend_library(library_id: str, admin: PlatformAdmin = Depends(get_admin), db: AsyncSession = Depends(get_db)):
    return await _set_status(library_id, LibraryStatus.suspended, db)
