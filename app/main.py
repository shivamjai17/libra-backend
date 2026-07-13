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
            # Additive column backfill for pre-existing SQLite dev dbs only.
            # (A fresh Postgres/RDS gets the full schema from create_all above.)
            if conn.dialect.name == "sqlite":
                for ddl in [
                    "ALTER TABLE students ADD COLUMN active BOOLEAN DEFAULT 1",
                ]:
                    try:
                        await conn.exec_driver_sql(ddl)
                    except Exception:
                        pass  # column already exists
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


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "service": settings.app_name}
