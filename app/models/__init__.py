"""Import all models so SQLAlchemy metadata is fully populated."""
from app.models.catalog import Batch, Hall, Plan, Seat
from app.models.operations import ActivityLog, AttendanceLog, Notification, Payment
from app.models.student import Document, Note, Student
from app.models.tenant import Branch, BranchSettings, Library, Staff

__all__ = [
    "Library", "Branch", "BranchSettings", "Staff",
    "Plan", "Batch", "Hall", "Seat",
    "Student", "Document", "Note",
    "Payment", "AttendanceLog", "Notification", "ActivityLog",
]
