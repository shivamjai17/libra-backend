from datetime import datetime

from pydantic import BaseModel

from app.models.enums import DeliveryStatus, NotificationChannel, NotificationType
from app.schemas.common import ORMModel


class NotificationCreate(BaseModel):
    student_id: str
    type: NotificationType
    channel: NotificationChannel = NotificationChannel.WhatsApp
    message: str | None = None  # if omitted, server renders from template


class NotificationOut(ORMModel):
    id: str
    student_id: str
    type: NotificationType
    channel: NotificationChannel
    message: str
    sent_at: datetime
    read: bool
    delivery_status: DeliveryStatus


class UnreadCount(BaseModel):
    unread: int
