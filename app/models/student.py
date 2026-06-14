"""Student plus per-student sub-resources (Document, Note)."""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantScoped, Timestamped, UUIDPrimaryKey


class Student(TenantScoped, Timestamped, Base):
    """The member. Identified like 'STU-2841'.

    `status` is intentionally NOT stored — it is derived at read time from
    membership_end + due_amount (see services.student.derive_status).
    """

    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # "STU-####"
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), index=True)
    email: Mapped[str | None] = mapped_column(String(180))

    plan_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("plans.id", ondelete="SET NULL"))
    batch_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("batches.id", ondelete="SET NULL"))
    hall_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("halls.id", ondelete="SET NULL"))
    seat_id: Mapped[str | None] = mapped_column(String(48))

    due_amount: Mapped[int] = mapped_column(Integer, default=0)
    joined_date: Mapped[date] = mapped_column(Date, default=date.today)
    membership_start: Mapped[date] = mapped_column(Date, default=date.today)
    membership_end: Mapped[date | None] = mapped_column(Date)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    plan: Mapped["object | None"] = relationship("Plan", lazy="joined")
    batch: Mapped["object | None"] = relationship("Batch", lazy="joined")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    notes: Mapped[list["Note"]] = relationship(back_populates="student", cascade="all, delete-orphan")


class Document(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "documents"

    student_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("students.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(120))  # e.g. "Aadhaar", "Photo", "Agreement"
    url: Mapped[str] = mapped_column(String(500))

    student: Mapped["Student"] = relationship(back_populates="documents")


class Note(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "notes"

    student_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("students.id", ondelete="CASCADE"), index=True
    )
    author: Mapped[str | None] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)

    student: Mapped["Student"] = relationship(back_populates="notes")
