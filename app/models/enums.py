"""Enumerations shared across models and schemas."""
from enum import Enum


class PlanPeriod(str, Enum):
    day = "day"
    week = "week"
    month = "month"
    quarter = "quarter"
    year = "year"


class SeatStatus(str, Enum):
    available = "available"
    occupied = "occupied"
    reserved = "reserved"
    maintenance = "maintenance"


class StudentStatus(str, Enum):
    active = "active"
    expired = "expired"
    due = "due"


class PaymentMethod(str, Enum):
    UPI = "UPI"
    Cash = "Cash"
    Card = "Card"
    Bank = "Bank"


class PaymentStatus(str, Enum):
    paid = "paid"
    pending = "pending"
    refunded = "refunded"


class AttendanceMethod(str, Enum):
    QR = "QR"
    Manual = "Manual"


class AttendanceStatus(str, Enum):
    inside = "inside"
    left = "left"


class NotificationType(str, Enum):
    welcome = "welcome"
    due = "due"
    pending = "pending"
    paid = "paid"


class NotificationChannel(str, Enum):
    WhatsApp = "WhatsApp"
    SMS = "SMS"
    Email = "Email"


class DeliveryStatus(str, Enum):
    queued = "queued"
    sent = "sent"
    delivered = "delivered"
    failed = "failed"


class StaffRole(str, Enum):
    Owner = "Owner"
    Manager = "Manager"
    FrontDesk = "FrontDesk"
    Accountant = "Accountant"


class AssetStatus(str, Enum):
    in_use = "in_use"
    available = "available"
    maintenance = "maintenance"
    retired = "retired"
