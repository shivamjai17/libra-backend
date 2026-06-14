from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token, decode_token, verify_password
from app.models.tenant import Staff
from app.schemas.auth import CurrentUser, RefreshRequest, TokenPair

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    user = (
        await db.execute(select(Staff).where(Staff.email == form.username))
    ).scalar_one_or_none()
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
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
