"""Password hashing and JWT helpers."""
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_token(subject: str, expires_delta: timedelta, claims: dict[str, Any]) -> str:
    to_encode = {
        "sub": subject,
        "exp": datetime.now(timezone.utc) + expires_delta,
        "iat": datetime.now(timezone.utc),
        **claims,
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(subject: str, **claims: Any) -> str:
    return _create_token(
        subject, timedelta(minutes=settings.access_token_expire_minutes), {"type": "access", **claims}
    )


def create_refresh_token(subject: str, **claims: Any) -> str:
    return _create_token(
        subject, timedelta(days=settings.refresh_token_expire_days), {"type": "refresh", **claims}
    )


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:  # pragma: no cover - re-raised as auth error upstream
        raise ValueError("Invalid token") from exc
