"""Attendance: check-in/out and live/hourly summaries."""
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import TenantContext
from app.models.enums import AttendanceMethod, AttendanceStatus
from app.models.operations import AttendanceLog
from app.models.student import Student


async def check_in(
    db: AsyncSession, ctx: TenantContext, student_id: str, method: AttendanceMethod
) -> AttendanceLog:
    student = await db.get(Student, student_id)
    if student is None or student.branch_id != ctx.branch_id:
        raise HTTPException(status_code=404, detail="Student not found")

    now = datetime.now(timezone.utc)
    log = AttendanceLog(
        library_id=ctx.library_id,
        branch_id=ctx.branch_id,
        student_id=student_id,
        date=date.today(),
        check_in_at=now,
        seat_id=student.seat_id,
        method=method,
        status=AttendanceStatus.inside,
    )
    student.last_seen_at = now
    db.add(log)
    await db.flush()
    return log


async def check_out(db: AsyncSession, ctx: TenantContext, student_id: str) -> AttendanceLog:
    log = (
        await db.execute(
            select(AttendanceLog)
            .where(
                AttendanceLog.branch_id == ctx.branch_id,
                AttendanceLog.student_id == student_id,
                AttendanceLog.status == AttendanceStatus.inside,
            )
            .order_by(AttendanceLog.check_in_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if log is None:
        raise HTTPException(status_code=404, detail="No open check-in")
    log.check_out_at = datetime.now(timezone.utc)
    log.status = AttendanceStatus.left
    await db.flush()
    return log


async def summary(db: AsyncSession, ctx: TenantContext) -> dict:
    inside_now = await db.scalar(
        select(func.count())
        .select_from(AttendanceLog)
        .where(
            AttendanceLog.branch_id == ctx.branch_id,
            AttendanceLog.status == AttendanceStatus.inside,
        )
    )
    today_total = await db.scalar(
        select(func.count(func.distinct(AttendanceLog.student_id))).where(
            AttendanceLog.branch_id == ctx.branch_id, AttendanceLog.date == date.today()
        )
    )
    rows = (
        await db.execute(
            select(AttendanceLog.check_in_at).where(
                AttendanceLog.branch_id == ctx.branch_id, AttendanceLog.date == date.today()
            )
        )
    ).scalars().all()
    buckets: dict[str, int] = {}
    for ts in rows:
        hour = ts.strftime("%H")
        buckets[hour] = buckets.get(hour, 0) + 1
    hourly = [{"hour": h, "count": c} for h, c in sorted(buckets.items())]
    return {"inside_now": inside_now or 0, "today_total": today_total or 0, "hourly": hourly}
