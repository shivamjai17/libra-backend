"""Inventory / asset tracking, scoped per branch."""
from datetime import date

from sqlalchemy import Date, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TenantScoped, Timestamped, UUIDPrimaryKey
from app.models.enums import AssetStatus


class Asset(UUIDPrimaryKey, TenantScoped, Timestamped, Base):
    """A physical asset owned by a branch (furniture, computers, AC, etc.)."""

    __tablename__ = "assets"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(60), default="General")
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[AssetStatus] = mapped_column(default=AssetStatus.in_use)
    location: Mapped[str | None] = mapped_column(String(120))
    unit_cost: Mapped[int] = mapped_column(Integer, default=0)
    purchase_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
