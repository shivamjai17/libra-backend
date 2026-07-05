from datetime import date

from pydantic import BaseModel

from app.models.enums import AssetStatus
from app.schemas.common import ORMModel


class AssetBase(BaseModel):
    name: str
    category: str = "General"
    quantity: int = 1
    status: AssetStatus = AssetStatus.in_use
    location: str | None = None
    unit_cost: int = 0
    purchase_date: date | None = None
    notes: str | None = None


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    quantity: int | None = None
    status: AssetStatus | None = None
    location: str | None = None
    unit_cost: int | None = None
    purchase_date: date | None = None
    notes: str | None = None


class AssetOut(ORMModel, AssetBase):
    id: str
