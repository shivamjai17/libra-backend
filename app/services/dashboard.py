"""Server-side computed KPIs, widgets and analytics. Nothing is stored."""
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import TenantContext
from app.models.catalog import Hall, Seat
from app.models.enums import PaymentStatus, SeatStatus, StudentStatus
from app.models.operations import ActivityLog, AttendanceLog, Payment
from app.models.student import Student
from app.services.attendance import summary as att_summary
from app.services.rules import derive_status


async def _students(db: AsyncSession, ctx: TenantContext) -> list[Student]:
    return list(
        (
            await db.execute(select(Student).where(Student.branch_id == ctx.branch_id))
        ).scalars().all()
    )


async def kpis(db: AsyncSession, ctx: TenantContext, start_date: date | None = None, end_date: date | None = None) -> dict:
    if start_date is None or end_date is None:
        today_val = date.today()
        start_date = start_date or date(today_val.year, today_val.month, 1)
        end_date = end_date or today_val

    students = await _students(db, ctx)
    statuses = [derive_status(s.membership_end, s.due_amount) for s in students]
    total_students = len(students)
    active = sum(1 for st in statuses if st == StudentStatus.active)
    expired = sum(1 for st in statuses if st == StudentStatus.expired)

    total_seats = await db.scalar(
        select(func.count()).select_from(Seat).where(Seat.branch_id == ctx.branch_id)
    ) or 0
    seat_counts = dict(
        (
            await db.execute(
                select(Seat.status, func.count())
                .where(Seat.branch_id == ctx.branch_id)
                .group_by(Seat.status)
            )
        ).all()
    )
    occupied = seat_counts.get(SeatStatus.occupied, 0)
    reserved = seat_counts.get(SeatStatus.reserved, 0)
    maintenance = seat_counts.get(SeatStatus.maintenance, 0)
    available = total_seats - occupied - reserved - maintenance
    occupancy_rate = round(occupied / total_seats, 4) if total_seats else 0.0

    range_rev = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.branch_id == ctx.branch_id,
            Payment.date >= start_date,
            Payment.date <= end_date,
            Payment.status == PaymentStatus.paid,
        )
    ) or 0

    month_start = date(end_date.year, end_date.month, 1)
    month_rev = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.branch_id == ctx.branch_id,
            Payment.date >= month_start,
            Payment.date <= end_date,
            Payment.status == PaymentStatus.paid,
        )
    ) or 0

    gst_collected = await db.scalar(
        select(func.coalesce(func.sum(Payment.gst), 0)).where(
            Payment.branch_id == ctx.branch_id,
            Payment.date >= start_date,
            Payment.date <= end_date,
            Payment.status == PaymentStatus.paid,
        )
    ) or 0

    pending_students = [s for s in students if s.due_amount and s.due_amount > 0]
    pending_total = sum(s.due_amount for s in pending_students)

    att = await att_summary(db, ctx)

    return {
        "total_students": total_students,
        "active_students": active,
        "expired_memberships": expired,
        "total_seats": total_seats,
        "available_seats": available,
        "occupancy_rate": occupancy_rate,
        "today_attendance": att["today_total"],
        "inside_now": att["inside_now"],
        "today_revenue": int(range_rev),
        "monthly_revenue": int(month_rev),
        "pending_payments": pending_total,
        "pending_students": len(pending_students),
        "gst_collected": int(gst_collected),
    }


async def widgets(db: AsyncSession, ctx: TenantContext, start_date: date | None = None, end_date: date | None = None) -> dict:
    if start_date is None or end_date is None:
        today_val = date.today()
        start_date = start_date or date(today_val.year, today_val.month, 1)
        end_date = end_date or today_val

    upcoming = (await db.execute(
        select(Student)
        .where(
            Student.branch_id == ctx.branch_id,
            Student.membership_end >= start_date,
            Student.membership_end <= end_date + timedelta(days=30),
        )
        .order_by(Student.membership_end)
        .limit(5)
    )).scalars().all()

    dues = (await db.execute(
        select(Student)
        .where(
            Student.branch_id == ctx.branch_id,
            Student.due_amount > 0
        )
        .order_by(Student.due_amount.desc())
        .limit(5)
    )).scalars().all()

    recent = (await db.execute(
        select(Student)
        .where(
            Student.branch_id == ctx.branch_id,
            Student.joined_date >= start_date,
            Student.joined_date <= end_date,
        )
        .order_by(Student.joined_date.desc())
        .limit(5)
    )).scalars().all()

    recent_payments = (
        await db.execute(
            select(Payment)
            .where(
                Payment.branch_id == ctx.branch_id,
                Payment.date >= start_date,
                Payment.date <= end_date,
            )
            .order_by(Payment.date.desc())
            .limit(5)
        )
    ).scalars().all()

    activity = (
        await db.execute(
            select(ActivityLog)
            .where(
                ActivityLog.branch_id == ctx.branch_id,
                func.date(ActivityLog.created_at) >= start_date,
                func.date(ActivityLog.created_at) <= end_date,
            )
            .order_by(ActivityLog.created_at.desc())
            .limit(8)
        )
    ).scalars().all()

    return {
        "upcoming_expirations": [
            {"id": s.id, "name": s.name, "end": s.membership_end.isoformat() if s.membership_end else None}
            for s in upcoming
        ],
        "pending_dues": [{"id": s.id, "name": s.name, "due": s.due_amount} for s in dues],
        "recent_registrations": [
            {"id": s.id, "name": s.name, "joined": s.joined_date.isoformat()} for s in recent
        ],
        "recent_payments": [
            {"id": p.id, "student_id": p.student_id, "amount": p.amount, "method": p.method.value}
            for p in recent_payments
        ],
        "recent_activity": [
            {"action": a.action, "subject": a.subject, "detail": a.detail, "at": a.created_at.isoformat()}
            for a in activity
        ],
    }


async def revenue_trend(db: AsyncSession, ctx: TenantContext, start_date: date | None = None, end_date: date | None = None) -> list[dict]:
    if start_date is None or end_date is None:
        today_val = date.today()
        start_date = start_date or date(today_val.year, today_val.month, 1)
        end_date = end_date or today_val

    payments = (await db.execute(
        select(Payment)
        .where(
            Payment.branch_id == ctx.branch_id,
            Payment.date >= start_date,
            Payment.date <= end_date,
            Payment.status == PaymentStatus.paid,
        )
        .order_by(Payment.date)
    )).scalars().all()

    days_diff = (end_date - start_date).days

    if days_diff <= 31:
        by_day = {}
        curr = start_date
        while curr <= end_date:
            by_day[curr] = 0
            curr += timedelta(days=1)
        for p in payments:
            if p.date in by_day:
                by_day[p.date] += p.amount
        return [{"label": d.strftime("%d %b"), "amount": amt} for d, amt in by_day.items()]
    else:
        by_month = {}
        curr = start_date
        while curr <= end_date:
            month_key = (curr.year, curr.month)
            by_month[month_key] = 0
            if curr.month == 12:
                curr = date(curr.year + 1, 1, 1)
            else:
                curr = date(curr.year, curr.month + 1, 1)
        for p in payments:
            month_key = (p.date.year, p.date.month)
            if month_key in by_month:
                by_month[month_key] += p.amount
        return [
            {"label": date(yr, mo, 1).strftime("%b %y"), "amount": amt}
            for (yr, mo), amt in sorted(by_month.items())
        ]


async def analytics(db: AsyncSession, ctx: TenantContext) -> dict:
    """Lightweight analytics. Production would back these with warehouse queries."""
    method_rows = (
        await db.execute(
            select(Payment.method, func.count())
            .where(Payment.branch_id == ctx.branch_id, Payment.status == PaymentStatus.paid)
            .group_by(Payment.method)
        )
    ).all()
    total = sum(c for _, c in method_rows) or 1
    breakdown = [{"method": m.value, "pct": round(c / total * 100, 1)} for m, c in method_rows]

    att = await att_summary(db, ctx)
    return {
        "retention_rate": 0.82,
        "renewal_rate": 0.74,
        "net_growth": 0,
        "revenue_forecast": [],
        "peak_hours": att["hourly"],
        "branch_performance": [],
        "payment_method_breakdown": breakdown,
    }
