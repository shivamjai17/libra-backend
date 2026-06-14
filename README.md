# LibraDesk — Backend (FastAPI)

Multi-branch study-center / library management SaaS API. Implements the data model,
derived values, business rules, notification flow, and REST surface from
`LibraDesk_Backend_Spec.md`.

## Stack

- **FastAPI** + **Uvicorn**
- **SQLAlchemy 2.0** (async) — PostgreSQL (`asyncpg`) in prod, **SQLite (`aiosqlite`) for zero-config local dev**
- **Pydantic v2** schemas
- **JWT** auth (access + refresh), **bcrypt** password hashing
- **Alembic** migrations

## Architecture

```
app/
  core/          config, async DB engine/session, security (JWT + hashing)
  models/        SQLAlchemy ORM — base mixins (UUID, timestamps, tenant-scope) + 12 entities
  schemas/       Pydantic request/response models
  services/      business logic (onboarding, seats, payments, attendance, notifications, dashboard)
  api/v1/        deps (auth + tenant scope) + routers, aggregated in router.py
  main.py        app factory + CORS + lifespan
scripts/seed.py  realistic demo data (StudyHub Reading Center, 5 branches, 12 students)
alembic/         async migration environment
tests/           pytest API tests
```

### Multi-tenancy

Shared database, **row-level isolation**. Every operational table carries `library_id`
and `branch_id` (see `models/base.py::TenantScoped`). The active branch is resolved per
request from the **`X-Branch-Id`** header (the UI branch switcher) and validated against
the authenticated user's library in `api/v1/deps.py::get_tenant`. This scales for many
small tenants and can migrate to schema-per-tenant later without touching business logic.

### Derived values are never stored

Student `status` and all dashboard KPIs (occupancy, revenue, GST, retention…) are
**computed server-side** (`services/rules.py`, `services/dashboard.py`) to avoid drift,
exactly as the spec requires.

## Quick start (local, SQLite — no DB to install)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m scripts.seed          # creates libradesk.db with demo data
uvicorn app.main:app --reload   # http://localhost:8000/docs
```

Login: **owner@studyhub.in** / **studyhub123**

Send `X-Branch-Id: <branch-id>` to scope requests to a branch (defaults to the user's
home branch). Fetch branch IDs from `GET /api/v1/libraries/{library_id}/branches`.

## Run with Docker (PostgreSQL)

```bash
docker compose up --build   # API on :8000, Postgres on :5432, auto-migrated + seeded
```

## Migrations

```bash
alembic revision --autogenerate -m "init"
alembic upgrade head
```

## Tests

```bash
python -m scripts.seed   # ensure demo data exists
pytest
```

## Money & notifications — production notes

- **Money** is stored as integers in a single unit; format ₹ / lakhs in the UI layer only.
  For production, migrate to minor units (paise) — see `models/catalog.py`.
- **Notifications** are queued + logged here (`delivery_status = queued`). Real delivery
  needs provider integrations (WhatsApp Business API / SMS gateway / SMTP) plus delivery
  webhooks to advance `delivery_status`.

## API surface (v1)

`auth` (login / refresh / me) · `dashboard` · `analytics` · `students` (+ notes) ·
`plans` · `batches` · `halls` · `seats` (assign / release / transfer / status) ·
`attendance` (checkin / checkout / summary) · `payments` (+ refund) ·
`notifications` (+ unread-count / read-all) · `settings` (profile / payments) · branches.

Full interactive docs at `/docs`.
