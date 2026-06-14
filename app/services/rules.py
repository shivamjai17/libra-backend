"""Pure business-rule helpers: membership math, status derivation, GST."""
from datetime import date, timedelta

from app.models.enums import PlanPeriod, StudentStatus

_PERIOD_DAYS = {
    PlanPeriod.day: 1,
    PlanPeriod.week: 7,
    PlanPeriod.month: 30,
    PlanPeriod.quarter: 91,
    PlanPeriod.year: 365,
}


def membership_end(start: date, period: PlanPeriod) -> date:
    """start + plan.period. Uses calendar-friendly day counts."""
    return start + timedelta(days=_PERIOD_DAYS[period])


def derive_status(membership_end_date: date | None, due_amount: int, today: date | None = None) -> StudentStatus:
    """Derived student status (never stored).

    - active  : membership valid AND no dues
    - due     : has an outstanding balance
    - expired : membership lapsed
    """
    today = today or date.today()
    if due_amount and due_amount > 0:
        return StudentStatus.due
    if membership_end_date is not None and membership_end_date < today:
        return StudentStatus.expired
    return StudentStatus.active


def compute_gst(amount: int, gst_rate_pct: float) -> int:
    """gst = round(amount * rate/100). Net and gst stored separately."""
    return round(amount * gst_rate_pct / 100)
