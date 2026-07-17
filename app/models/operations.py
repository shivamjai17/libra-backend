"""Operational logs: Payment, AttendanceLog, Notification, ActivityLog."""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TenantScoped, Timestamped, UUIDPrimaryKey
from app.models.enums import (
    AttendanceMethod,
    AttendanceStatus,
    DeliveryStatus,
    NotificationChannel,
    NotificationType,
    PaymentMethod,
    PaymentStatus,
)


class Payment(TenantScoped, Timestamped, Base):
    """Transaction / Invoice. Identified like 'INV-4821'."""

    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # "INV-####"
    student_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("students.id", ondelete="CASCADE"), index=True
    )
    plan_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("plans.id", ondelete="SET NULL"))
    date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    method: Mapped[PaymentMethod] = mapped_column(default=PaymentMethod.UPI)
    amount: Mapped[int] = mapped_column(Integer)  # net amount
    gst: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[PaymentStatus] = mapped_column(default=PaymentStatus.paid, index=True)
    description: Mapped[str | None] = mapped_column(String(240))
    receipt_url: Mapped[str | None] = mapped_column(String(500))
    receipt_token: Mapped[str | None] = mapped_column(String(24), index=True)


class AttendanceLog(UUIDPrimaryKey, TenantScoped, Timestamped, Base):
    """One row per check-in/out event."""

    __tablename__ = "attendance_logs"

    student_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("students.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    check_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seat_id: Mapped[str | None] = mapped_column(String(48))
    method: Mapped[AttendanceMethod] = mapped_column(default=AttendanceMethod.Manual)
    status: Mapped[AttendanceStatus] = mapped_column(default=AttendanceStatus.inside, index=True)


class Notification(UUIDPrimaryKey, TenantScoped, Timestamped, Base):
    """A message sent (or queued) to a student."""

    __tablename__ = "notifications"

    student_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("students.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[NotificationType] = mapped_column(index=True)
    channel: Mapped[NotificationChannel] = mapped_column(default=NotificationChannel.WhatsApp)
    message: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    delivery_status: Mapped[DeliveryStatus] = mapped_column(default=DeliveryStatus.queued)


class ActivityLog(UUIDPrimaryKey, TenantScoped, Timestamped, Base):
    """Audit feed powering the dashboard 'Recent Activity' widget."""

    __tablename__ = "activity_logs"

    actor: Mapped[str | None] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(60))  # e.g. "student.created", "payment.collected"
    subject: Mapped[str | None] = mapped_column(String(160))
    detail: Mapped[str | None] = mapped_column(Text)
