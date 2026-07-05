"""Memberships overview: plan distribution, renewals and expirations.

Derived entirely from existing Student / Plan / Payment data (no new tables).
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import TenantContext, get_tenant
from app.core.database import get_db
from app.models.catalog import Plan
from app.models.enums import PaymentStatus
from app.models.operations import Payment
from app.models.student import Student
from app.services.rules import derive_status
from app.schemas.common import ORMModel


class PlanBreakdown(ORMModel):
    id: str
    name: str
    price: int
    period: str
    members: int
    revenue: int


class MemberRow(ORMModel):
    id: str
    name: str
    plan: str | None = None
    end: str | None = None
    days_left: int | None = None


class RenewalRow(ORMModel):
    id: str
    student_id: str
    name: str
    plan: str | None = None
    amount: int
    date: str


class MembershipsOverview(ORMModel):
    active: int
    expiring_soon: int
    expired: int
    total_members: int
    plans: list[PlanBreakdown]
    upcoming_expirations: list[MemberRow]
    recent_renewals: list[RenewalRow]


router = APIRouter(tags=["memberships"])


@router.get("/memberships/overview", response_model=MembershipsOverview)
async def memberships_overview(ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    today = date.today()
    soon = today + timedelta(days=14)

    students = (await db.execute(
        select(Student).where(Student.branch_id == ctx.branch_id)
    )).scalars().all()
    plans = (await db.execute(
        select(Plan).where(Plan.branch_id == ctx.branch_id)
    )).scalars().all()
    plan_by_id = {p.id: p for p in plans}

    active = expiring = expired = 0
    members_per_plan: dict[str, int] = {}
    upcoming: list[MemberRow] = []

    for s in students:
        st = derive_status(s.membership_end, s.due_amount, today)
        if st.value == "expired":
            expired += 1
        else:
            active += 1
        if s.plan_id:
            members_per_plan[s.plan_id] = members_per_plan.get(s.plan_id, 0) + 1
        if s.membership_end and today <= s.membership_end <= soon:
            expiring += 1
            upcoming.append(MemberRow(
                id=s.id, name=s.name,
                plan=plan_by_id[s.plan_id].name if s.plan_id in plan_by_id else None,
                end=s.membership_end.isoformat(),
                days_left=(s.membership_end - today).days,
            ))

    upcoming.sort(key=lambda m: m.days_left if m.days_left is not None else 999)

    # revenue per plan (paid)
    rev_rows = (await db.execute(
        select(Payment.plan_id, Payment.amount).where(
            Payment.branch_id == ctx.branch_id, Payment.status == PaymentStatus.paid
        )
    )).all()
    rev_per_plan: dict[str, int] = {}
    for pid, amt in rev_rows:
        if pid:
            rev_per_plan[pid] = rev_per_plan.get(pid, 0) + (amt or 0)

    plan_breakdown = [
        PlanBreakdown(
            id=p.id, name=p.name, price=p.price, period=p.period.value,
            members=members_per_plan.get(p.id, 0), revenue=rev_per_plan.get(p.id, 0),
        )
        for p in plans
    ]
    plan_breakdown.sort(key=lambda p: p.members, reverse=True)

    # recent renewals (latest paid payments)
    recent = (await db.execute(
        select(Payment).where(
            Payment.branch_id == ctx.branch_id, Payment.status == PaymentStatus.paid
        ).order_by(Payment.date.desc()).limit(8)
    )).scalars().all()
    name_by_id = {s.id: s.name for s in students}
    renewals = [
        RenewalRow(
            id=p.id, student_id=p.student_id,
            name=name_by_id.get(p.student_id, p.student_id),
            plan=plan_by_id[p.plan_id].name if p.plan_id in plan_by_id else None,
            amount=p.amount, date=p.date.isoformat(),
        )
        for p in recent
    ]

    return MembershipsOverview(
        active=active, expiring_soon=expiring, expired=expired,
        total_members=len(students), plans=plan_breakdown,
        upcoming_expirations=upcoming[:8], recent_renewals=renewals,
    )
