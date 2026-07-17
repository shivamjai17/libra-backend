"""Build + store a receipt PDF for a payment, and mint its short link."""
import logging
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.catalog import Plan
from app.models.operations import Payment
from app.models.student import Student
from app.models.tenant import Library
from app.services import storage
from app.services.receipts import build_receipt_pdf

logger = logging.getLogger(__name__)


def short_link(token: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/r/{token}"


async def generate_for_payment(db: AsyncSession, payment: Payment) -> str | None:
    """Render the receipt, store it, save the token/url on the payment.

    Returns the short link, or None if it couldn't be produced. Never raises —
    a receipt problem must not roll back a collected payment.
    """
    try:
        student = await db.get(Student, payment.student_id)
        library = await db.get(Library, payment.library_id)
        plan = await db.get(Plan, payment.plan_id) if payment.plan_id else None

        logo_bytes = None
        if library and library.logo_url:
            key = library.logo_url.split(".amazonaws.com/")[-1] if "amazonaws.com/" in library.logo_url else None
            if key is None and "/media/" in library.logo_url:
                key = library.logo_url.split("/media/", 1)[1]
            if key:
                logo_bytes = storage.get_bytes(key)

        period = None
        if student and student.membership_start and student.membership_end:
            period = f"{student.membership_start.strftime('%d %b %Y')} - {student.membership_end.strftime('%d %b %Y')}"

        pdf = build_receipt_pdf(
            library_name=library.name if library else "Writtly",
            library_address=library.address if library else None,
            gst_number=library.gst_number if library else None,
            logo_bytes=logo_bytes,
            receipt_no=payment.id,
            receipt_date=payment.date,
            student_name=student.name if student else payment.student_id,
            student_id=payment.student_id,
            plan_name=plan.name if plan else None,
            period=period,
            amount=payment.amount,
            gst=payment.gst or 0,
            method=payment.method.value,
            accent=(library.accent_color if library and library.accent_color else "#0f7c5a"),
        )

        url = storage.store_receipt(pdf, payment.library_id, payment.id)
        if not url:
            return None

        payment.receipt_url = url
        payment.receipt_token = secrets.token_urlsafe(8)[:12]
        await db.flush()
        return short_link(payment.receipt_token)
    except Exception as exc:  # noqa: BLE001
        logger.error("Receipt generation failed for %s: %s", payment.id, exc)
        return None
