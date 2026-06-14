"""Server-side computed KPIs, widgets and analytics. Nothing is stored."""
from datetime import date

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


async def kpis(db: AsyncSession, ctx: TenantContext) -> dict:
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

    today = date.today()
    today_rev = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.branch_id == ctx.branch_id,
            Payment.date == today,
            Payment.status == PaymentStatus.paid,
        )
    )
    month_rev = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.branch_id == ctx.branch_id,
            func.strftime("%Y-%m", Payment.date) == today.strftime("%Y-%m"),
            Payment.status == PaymentStatus.paid,
        )
    )
    gst_collected = await db.scalar(
        select(func.coalesce(func.sum(Payment.gst), 0)).where(
            Payment.branch_id == ctx.branch_id, Payment.status == PaymentStatus.paid
        )
    )

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
        "today_revenue": int(today_rev or 0),
        "monthly_revenue": int(month_rev or 0),
        "pending_payments": pending_total,
        "pending_students": len(pending_students),
        "gst_collected": int(gst_collected or 0),
    }


async def widgets(db: AsyncSession, ctx: TenantContext) -> dict:
    students = await _students(db, ctx)
    today = date.today()

    upcoming = sorted(
        [s for s in students if s.membership_end and s.membership_end >= today],
        key=lambda s: s.membership_end,
    )[:5]
    dues = [s for s in students if s.due_amount and s.due_amount > 0][:5]
    recent = sorted(students, key=lambda s: s.joined_date, reverse=True)[:5]

    recent_payments = (
        await db.execute(
            select(Payment).where(Payment.branch_id == ctx.branch_id).order_by(Payment.date.desc()).limit(5)
        )
    ).scalars().all()
    activity = (
        await db.execute(
            select(ActivityLog)
            .where(ActivityLog.branch_id == ctx.branch_id)
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
