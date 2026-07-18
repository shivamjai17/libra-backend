"""Generate human-friendly sequential IDs.

Student IDs and invoice IDs are GLOBAL primary keys, so they must be unique
across every branch and library. We derive the next value from the current
maximum existing numeric id (not a row count), which is collision-safe even
after deletions or across branches.
"""
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operations import Payment
from app.models.student import Student

STUDENT_BASE = 2800
INVOICE_BASE = 4800


def _max_numeric(values, prefix: str = "") -> int:
    """Highest integer found among ids like '2801' or 'INV-4821'."""
    best = 0
    for v in values:
        if v is None:
            continue
        m = re.search(r"(\d+)$", str(v))
        if m:
            best = max(best, int(m.group(1)))
    return best


async def next_student_id(db: AsyncSession, branch_id: str | None = None) -> str:
    ids = (await db.execute(select(Student.id))).scalars().all()
    nxt = max(STUDENT_BASE, _max_numeric(ids)) + 1
    return str(nxt)


async def next_invoice_id(db: AsyncSession, branch_id: str | None = None) -> str:
    ids = (await db.execute(select(Payment.id))).scalars().all()
    nxt = max(INVOICE_BASE, _max_numeric(ids)) + 1
    return f"INV-{nxt}"
