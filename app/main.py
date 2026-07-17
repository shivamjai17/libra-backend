"""Writtly FastAPI application entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup when enabled (idempotent — only makes missing
    # tables). Lets a fresh RDS come up without a manual migration step.
    if settings.environment == "development" or settings.create_tables_on_startup:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Additive column backfill for tables that already exist.
            # (create_all only creates missing tables, not missing columns.)
            if conn.dialect.name == "sqlite":
                for ddl in [
                    "ALTER TABLE students ADD COLUMN active BOOLEAN DEFAULT 1",
                    "ALTER TABLE payments ADD COLUMN receipt_url VARCHAR(500)",
                    "ALTER TABLE payments ADD COLUMN receipt_token VARCHAR(24)",
                ]:
                    try:
                        await conn.exec_driver_sql(ddl)
                    except Exception:
                        pass  # column already exists
            else:
                # Postgres supports IF NOT EXISTS, so these are safe to re-run.
                for ddl in [
                    "ALTER TABLE students ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE",
                    "ALTER TABLE payments ADD COLUMN IF NOT EXISTS receipt_url VARCHAR(500)",
                    "ALTER TABLE payments ADD COLUMN IF NOT EXISTS receipt_token VARCHAR(24)",
                ]:
                    try:
                        await conn.exec_driver_sql(ddl)
                    except Exception as exc:
                        import logging
                        logging.getLogger(__name__).warning("migration skipped: %s (%s)", ddl, exc)
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs",
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)

# Short receipt links live at the domain root (keeps SMS short): /r/{token}
from app.api.v1.routes import receipts as _receipts  # noqa: E402

app.include_router(_receipts.router)

# Serve locally-stored media in development (S3 serves it in production).
if not settings.s3_configured:
    import os as _os
    from fastapi.staticfiles import StaticFiles  # noqa: E402

    _os.makedirs("media", exist_ok=True)
    app.mount("/media", StaticFiles(directory="media"), name="media")


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "service": settings.app_name}
