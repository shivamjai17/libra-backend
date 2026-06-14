"""Admin-configurable catalog: Plan, Batch, Hall, Seat."""
from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantScoped, Timestamped, UUIDPrimaryKey
from app.models.enums import PlanPeriod, SeatStatus


class Plan(UUIDPrimaryKey, TenantScoped, Timestamped, Base):
    """Membership plan students choose at onboarding (Settings -> Plans)."""

    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    price: Mapped[int] = mapped_column(Integer, default=0)  # integer minor/major units; see README
    period: Mapped[PlanPeriod] = mapped_column(default=PlanPeriod.month)
    seat_included: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Batch(UUIDPrimaryKey, TenantScoped, Timestamped, Base):
    """Study time slot students are assigned to (Settings -> Batches)."""

    __tablename__ = "batches"

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    start_time: Mapped[str] = mapped_column(String(16))  # "06:00"
    end_time: Mapped[str] = mapped_column(String(16))
    color: Mapped[str] = mapped_column(String(16), default="green")  # green/blue/purple/amber/red
    capacity: Mapped[int | None] = mapped_column(Integer)  # optional cap


class Hall(UUIDPrimaryKey, TenantScoped, Timestamped, Base):
    """A room with a seat grid (Settings -> Seat Layout)."""

    __tablename__ = "halls"

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    floor: Mapped[str] = mapped_column(String(80), default="Ground Floor")
    rows: Mapped[int] = mapped_column(Integer, default=5)
    cols: Mapped[int] = mapped_column(Integer, default=10)

    seats: Mapped[list["Seat"]] = relationship(back_populates="hall", cascade="all, delete-orphan")

    @property
    def capacity(self) -> int:
        return self.rows * self.cols


class Seat(TenantScoped, Timestamped, Base):
    """An individual seat within a Hall. Identified like 'A-14'."""

    __tablename__ = "seats"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)  # "<hallId>:A-14"
    code: Mapped[str] = mapped_column(String(8))  # "A-14"
    hall_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("halls.id", ondelete="CASCADE"), index=True
    )
    row: Mapped[str] = mapped_column(String(2))
    number: Mapped[int] = mapped_column(Integer)
    status: Mapped[SeatStatus] = mapped_column(default=SeatStatus.available)
    student_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("students.id", ondelete="SET NULL"), index=True
    )
    occupied_since: Mapped[str | None] = mapped_column(String(24))

    hall: Mapped["Hall"] = relationship(back_populates="seats")
