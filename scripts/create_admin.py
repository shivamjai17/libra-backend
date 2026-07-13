"""Create or update the platform admin (SaaS operator) for production.

Usage (from the backend folder, venv active):
    ADMIN_EMAIL=admin@writtly.in ADMIN_PASSWORD='a-strong-password' \
        python -m scripts.create_admin

Without env vars it defaults to admin@writtly.in / change this. Running it
again updates the password for that email — safe to re-run.
"""
import asyncio
import os

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, Base, engine
from app.core.security import hash_password
from app.models.admin import PlatformAdmin


async def main() -> None:
    email = os.getenv("ADMIN_EMAIL", "admin@writtly.in")
    password = os.getenv("ADMIN_PASSWORD", "change-this-now")
    name = os.getenv("ADMIN_NAME", "Writtly Admin")

    # Make sure tables exist (safe if they already do).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        existing = (await db.execute(
            select(PlatformAdmin).where(PlatformAdmin.email == email)
        )).scalar_one_or_none()
        if existing:
            existing.hashed_password = hash_password(password)
            existing.active = True
            action = "updated"
        else:
            db.add(PlatformAdmin(
                name=name, email=email,
                hashed_password=hash_password(password), active=True,
            ))
            action = "created"
        await db.commit()
    print(f"Platform admin {action}: {email}")


if __name__ == "__main__":
    asyncio.run(main())
