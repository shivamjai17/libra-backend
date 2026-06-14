"""Generate human-friendly sequential IDs scoped to a branch."""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operations import Payment
from app.models.student import Student


async def next_student_id(db: AsyncSession, branch_id: str) -> str:
    count = await db.scalar(
        select(func.count()).select_from(Student).where(Student.branch_id == branch_id)
    )
    return f"STU-{2800 + (count or 0) + 1}"


async def next_invoice_id(db: AsyncSession, branch_id: str) -> str:
    count = await db.scalar(
        select(func.count()).select_from(Payment).where(Payment.branch_id == branch_id)
    )
    return f"INV-{4800 + (count or 0) + 1}"
