from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.core.security import (
    create_access_token, create_refresh_token, decode_token, hash_password, verify_password,
)
from app.models.enums import LibraryStatus, StaffRole
from app.models.tenant import Branch, BranchSettings, Library, Staff
from app.schemas.auth import (
    CurrentUser, RefreshRequest, RegisterRequest, RegisterResponse, TokenPair,
)

router = APIRouter(prefix="/auth", tags=["auth"])

APPROVAL_MESSAGE = "Your institute is awaiting admin approval. You'll be able to sign in once it's approved."


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Public self-service signup. Creates a PENDING library + first branch + owner."""
    dupe = (await db.execute(select(Staff).where(Staff.email == payload.email))).scalar_one_or_none()
    if dupe:
        raise HTTPException(409, "An account with this email already exists")

    lib = Library(
        name=payload.institute_name, contact_phone=payload.phone, email=payload.email,
        address=payload.address, owner_name=payload.owner_name, plan=payload.plan,
        status=LibraryStatus.pending,
    )
    db.add(lib)
    await db.flush()

    branch = Branch(library_id=lib.id, name=payload.branch or "Main Branch", area="Main")
    db.add(branch)
    await db.flush()
    db.add(BranchSettings(branch_id=branch.id))

    db.add(Staff(
        library_id=lib.id, branch_id=branch.id, name=payload.owner_name, email=payload.email,
        hashed_password=hash_password(payload.password), role=StaffRole.Owner, active=True,
    ))
    await db.commit()
    return RegisterResponse(library_id=lib.id, status=lib.status.value, message=APPROVAL_MESSAGE)


@router.post("/login", response_model=TokenPair)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(Staff).where(Staff.email == form.username))).scalar_one_or_none()
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    library = await db.get(Library, user.library_id)
    if library is None or library.status != LibraryStatus.approved:
        detail = APPROVAL_MESSAGE
        if library and library.status == LibraryStatus.rejected:
            detail = "Your institute's registration was not approved. Please contact support."
        elif library and library.status == LibraryStatus.suspended:
            detail = "Your institute's account has been suspended. Please contact support."
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    claims = {"library_id": user.library_id, "branch_id": user.branch_id, "role": user.role.value}
    return TokenPair(
        access_token=create_access_token(user.id, **claims),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        data = decode_token(payload.refresh_token)
        if data.get("type") != "refresh":
            raise ValueError("not a refresh token")
        user = await db.get(Staff, data["sub"])
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    claims = {"library_id": user.library_id, "branch_id": user.branch_id, "role": user.role.value}
    return TokenPair(
        access_token=create_access_token(user.id, **claims),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=CurrentUser)
async def me(user: Staff = Depends(get_current_user)):
    return CurrentUser(
        id=user.id, name=user.name, email=user.email, role=user.role.value,
        library_id=user.library_id, branch_id=user.branch_id,
    )
