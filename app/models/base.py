"""Shared model mixins: UUID primary keys, timestamps, and tenant scoping."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class UUIDPrimaryKey:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class TenantScoped:
    """Every operational row is scoped to a library and a branch.

    This is the backbone of multi-tenancy: shared database, row-level isolation.
    All operational queries MUST filter by these columns (enforced in repositories).
    """

    library_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("libraries.id", ondelete="CASCADE"), index=True, nullable=False
    )
    branch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("branches.id", ondelete="CASCADE"), index=True, nullable=False
    )
