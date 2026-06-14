from pydantic import BaseModel, Field

from app.models.enums import PlanPeriod, SeatStatus
from app.schemas.common import ORMModel


# ---- Plan ----
class PlanBase(BaseModel):
    name: str
    price: int = 0
    period: PlanPeriod = PlanPeriod.month
    seat_included: bool = True
    active: bool = True


class PlanCreate(PlanBase):
    pass


class PlanUpdate(BaseModel):
    name: str | None = None
    price: int | None = None
    period: PlanPeriod | None = None
    seat_included: bool | None = None
    active: bool | None = None


class PlanOut(ORMModel, PlanBase):
    id: str


# ---- Batch ----
class BatchBase(BaseModel):
    name: str
    start_time: str = Field(examples=["06:00"])
    end_time: str = Field(examples=["11:00"])
    color: str = "green"
    capacity: int | None = None


class BatchCreate(BatchBase):
    pass


class BatchUpdate(BaseModel):
    name: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    color: str | None = None
    capacity: int | None = None


class BatchOut(ORMModel, BatchBase):
    id: str


# ---- Hall ----
class HallBase(BaseModel):
    name: str
    floor: str = "Ground Floor"
    rows: int = 5
    cols: int = 10


class HallCreate(HallBase):
    pass


class HallUpdate(BaseModel):
    name: str | None = None
    floor: str | None = None
    rows: int | None = None
    cols: int | None = None


class HallOut(ORMModel, HallBase):
    id: str
    capacity: int


# ---- Seat ----
class SeatOut(ORMModel):
    id: str
    code: str
    hall_id: str
    row: str
    number: int
    status: SeatStatus
    student_id: str | None = None
    occupied_since: str | None = None


class SeatAssign(BaseModel):
    student_id: str


class SeatTransfer(BaseModel):
    to_seat_id: str


class SeatStatusUpdate(BaseModel):
    status: SeatStatus
