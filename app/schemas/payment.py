from datetime import date

from pydantic import BaseModel

from app.models.enums import PaymentMethod, PaymentStatus
from app.schemas.common import ORMModel


class PaymentCreate(BaseModel):
    student_id: str
    amount: int
    method: PaymentMethod = PaymentMethod.UPI
    plan_id: str | None = None
    description: str | None = None


class PaymentOut(ORMModel):
    id: str
    student_id: str
    plan_id: str | None = None
    date: date
    method: PaymentMethod
    amount: int
    gst: int
    status: PaymentStatus
    description: str | None = None
    receipt_url: str | None = None
    receipt_token: str | None = None
