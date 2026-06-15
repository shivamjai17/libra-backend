"""Reusable API dependencies: DB session, current user, and tenant scope."""
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token
from app.models.tenant import Branch, Staff

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")


@dataclass
class TenantContext:
    """The resolved (library, branch, user) scope for the current request."""

    user: Staff
    library_id: str
    branch_id: str


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> Staff:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise cred_exc
        user_id = payload.get("sub")
    except ValueError as exc:
        raise cred_exc from exc

    user = await db.get(Staff, user_id)
    if user is None or not user.active:
        raise cred_exc
    return user


async def get_tenant(
    x_branch_id: str | None = Header(default=None, alias="X-Branch-Id"),
    user: Staff = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """Resolve the active branch for this request.

    The frontend sends the selected branch via the `X-Branch-Id` header
    (the branch switcher). The branch must belong to the user's library.
    """
    branch = None

    # 1. Try the requested branch from header
    if x_branch_id:
        branch = await db.get(Branch, x_branch_id)
        if branch and branch.library_id != user.library_id:
            raise HTTPException(status_code=403, detail="Branch not accessible")

    # 2. Try the user's default branch
    if not branch and user.branch_id:
        branch = await db.get(Branch, user.branch_id)
        if branch and branch.library_id != user.library_id:
            branch = None

    # 3. Fall back to the first branch in the library
    if not branch:
        result = await db.execute(
            select(Branch).where(Branch.library_id == user.library_id).limit(1)
        )
        branch = result.scalar_one_or_none()
        if branch is None:
            raise HTTPException(status_code=400, detail="No branch available for this account")

    return TenantContext(user=user, library_id=user.library_id, branch_id=branch.id)
