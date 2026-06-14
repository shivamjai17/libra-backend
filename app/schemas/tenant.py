from pydantic import BaseModel

from app.schemas.common import ORMModel


class BranchOut(ORMModel):
    id: str
    name: str
    area: str | None = None


class LibraryOut(ORMModel):
    id: str
    name: str
    contact_phone: str | None = None
    gst_number: str | None = None
    address: str | None = None
    timezone: str
    logo_url: str | None = None
    accent_color: str


class LibraryUpdate(BaseModel):
    name: str | None = None
    contact_phone: str | None = None
    gst_number: str | None = None
    address: str | None = None
    accent_color: str | None = None


class BranchSettingsOut(ORMModel):
    currency: str
    gst_rate_pct: float
    late_fee_per_day: int
    grace_period_days: int


class BranchSettingsUpdate(BaseModel):
    currency: str | None = None
    gst_rate_pct: float | None = None
    late_fee_per_day: int | None = None
    grace_period_days: int | None = None
