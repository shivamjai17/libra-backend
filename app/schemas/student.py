from datetime import date, datetime

from pydantic import BaseModel, EmailStr

from app.models.enums import PlanPeriod, StudentStatus
from app.schemas.common import ORMModel


class StudentCreate(BaseModel):
    name: str
    phone: str
    email: EmailStr | None = None
    plan_id: str
    batch_id: str
    hall_id: str | None = None
    seat_id: str | None = None  # if omitted and plan.seat_included, auto-assign
    duration: PlanPeriod | None = None  # overrides plan.period if provided
    initial_payment: int | None = None  # fee collected at signup


class StudentUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    plan_id: str | None = None
    batch_id: str | None = None


class DocumentOut(ORMModel):
    id: str
    label: str
    url: str
    created_at: datetime


class StudentOut(ORMModel):
    id: str
    name: str
    phone: str
    email: str | None = None
    plan_id: str | None = None
    batch_id: str | None = None
    hall_id: str | None = None
    seat_id: str | None = None
    due_amount: int
    joined_date: date
    membership_start: date
    membership_end: date | None = None
    # derived / denormalized for the UI
    status: StudentStatus
    plan_name: str | None = None
    batch_name: str | None = None


class StudentDetail(StudentOut):
    documents: list[DocumentOut] = []
