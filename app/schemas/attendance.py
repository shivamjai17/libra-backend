from datetime import datetime

from pydantic import BaseModel

from app.models.enums import AttendanceMethod, AttendanceStatus
from app.schemas.common import ORMModel


class CheckInRequest(BaseModel):
    student_id: str | None = None
    qr_token: str | None = None
    method: AttendanceMethod = AttendanceMethod.Manual


class CheckOutRequest(BaseModel):
    student_id: str


class AttendanceOut(ORMModel):
    id: str
    student_id: str
    check_in_at: datetime
    check_out_at: datetime | None = None
    seat_id: str | None = None
    method: AttendanceMethod
    status: AttendanceStatus


class AttendanceSummary(BaseModel):
    inside_now: int
    today_total: int
    hourly: list[dict]  # [{"hour": "09", "count": 42}, ...]
