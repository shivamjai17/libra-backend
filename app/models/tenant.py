"""Tenant-level models: Library (tenant), Branch, BranchSettings, Staff."""
from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import Timestamped, UUIDPrimaryKey
from app.models.enums import StaffRole


class Library(UUIDPrimaryKey, Timestamped, Base):
    """Top-level tenant account. One per customer organization."""

    __tablename__ = "libraries"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    gst_number: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(String(400))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    logo_url: Mapped[str | None] = mapped_column(String(400))
    accent_color: Mapped[str] = mapped_column(String(9), default="#0f7c5a")

    branches: Mapped[list["Branch"]] = relationship(back_populates="library", cascade="all, delete-orphan")


class Branch(UUIDPrimaryKey, Timestamped, Base):
    """A physical location belonging to a Library. Operational data is scoped here."""

    __tablename__ = "branches"

    library_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("libraries.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    area: Mapped[str | None] = mapped_column(String(160))

    library: Mapped["Library"] = relationship(back_populates="branches")
    settings: Mapped["BranchSettings"] = relationship(
        back_populates="branch", uselist=False, cascade="all, delete-orphan"
    )


class BranchSettings(UUIDPrimaryKey, Timestamped, Base):
    """Per-branch configuration (Settings -> Payments)."""

    __tablename__ = "branch_settings"

    branch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("branches.id", ondelete="CASCADE"), unique=True, index=True
    )
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    gst_rate_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=18)
    late_fee_per_day: Mapped[int] = mapped_column(Integer, default=50)
    grace_period_days: Mapped[int] = mapped_column(Integer, default=5)

    branch: Mapped["Branch"] = relationship(back_populates="settings")


class Staff(UUIDPrimaryKey, Timestamped, Base):
    """Team member with scoped permissions. Also the login account."""

    __tablename__ = "staff"

    library_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("libraries.id", ondelete="CASCADE"), index=True
    )
    branch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("branches.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[StaffRole] = mapped_column(default=StaffRole.Owner)
    permissions: Mapped[str | None] = mapped_column(String(800))  # CSV of custom perms
    active: Mapped[bool] = mapped_column(Boolean, default=True)
