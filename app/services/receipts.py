"""GST-compliant tax invoice PDF (A5 portrait), rendered with ReportLab.

Layout: library logo + name/address/GSTIN header, receipt meta, student and
plan details, an amount table with CGST/SGST split, and a footer note.
"""
import io
import logging
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

GREEN = colors.HexColor("#0f7c5a")
INK = colors.HexColor("#0e1b16")
MUTED = colors.HexColor("#5c6c64")
LINE = colors.HexColor("#dbe3df")

W, H = A5  # 148 x 210 mm


def _rupees(paise_or_rupees: int) -> str:
    return f"Rs {paise_or_rupees:,.0f}"


def build_receipt_pdf(
    *,
    library_name: str,
    library_address: str | None,
    gst_number: str | None,
    logo_bytes: bytes | None,
    receipt_no: str,
    receipt_date: date,
    student_name: str,
    student_id: str,
    plan_name: str | None,
    period: str | None,
    amount: int,
    gst: int,
    gst_rate: float = 18.0,
    method: str,
    accent: str = "#0f7c5a",
) -> bytes:
    """Render a receipt and return PDF bytes."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A5)
    accent_color = colors.HexColor(accent) if accent else GREEN

    y = H - 14 * mm

    # ---- Header: logo + library identity ----
    text_x = 14 * mm
    if logo_bytes:
        try:
            from reportlab.lib.utils import ImageReader

            img = ImageReader(io.BytesIO(logo_bytes))
            iw, ih = img.getSize()
            box = 16 * mm
            scale = min(box / iw, box / ih)
            c.drawImage(img, 14 * mm, y - box + 4 * mm, iw * scale, ih * scale,
                        mask="auto", preserveAspectRatio=True)
            text_x = 14 * mm + box + 4 * mm
        except Exception as exc:  # noqa: BLE001 — never fail a receipt over a logo
            logger.warning("Could not draw logo on receipt: %s", exc)

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(text_x, y, library_name[:38])
    c.setFont("Helvetica", 7.5)
    c.setFillColor(MUTED)
    line_y = y - 5 * mm
    if library_address:
        c.drawString(text_x, line_y, library_address[:60])
        line_y -= 3.6 * mm
    if gst_number:
        c.drawString(text_x, line_y, f"GSTIN: {gst_number}")

    # ---- Title band ----
    y -= 24 * mm
    c.setFillColor(accent_color)
    c.rect(0, y, W, 9 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(14 * mm, y + 3 * mm, "INVOICE")
    c.setFont("Helvetica", 8)
    c.drawRightString(W - 14 * mm, y + 3 * mm, f"{receipt_no}  |  {receipt_date.strftime('%d %b %Y')}")

    # ---- Student / plan details ----
    y -= 12 * mm
    rows = [
        ("Received from", student_name),
        ("Student ID", student_id),
        ("Plan", plan_name or "-"),
    ]
    if period:
        rows.append(("Period", period))
    rows.append(("Payment mode", method))

    c.setFont("Helvetica", 8.5)
    for label, value in rows:
        c.setFillColor(MUTED)
        c.drawString(14 * mm, y, label)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(48 * mm, y, str(value)[:44])
        c.setFont("Helvetica", 8.5)
        y -= 6 * mm

    # ---- Amount table ----
    y -= 4 * mm
    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(14 * mm, y, W - 14 * mm, y)
    y -= 7 * mm

    taxable = max(0, amount - gst)
    half_gst = gst / 2
    half_rate = (gst_rate / 2) if gst_rate else 0
    if gst > 0:
        money_rows = [
            ("Taxable value", _rupees(taxable), False),
            (f"CGST ({half_rate:g}%)", _rupees(half_gst), False),
            (f"SGST ({half_rate:g}%)", _rupees(half_gst), False),
        ]
    else:
        # No GST configured — show a clean single line, no tax split.
        money_rows = [
            ("Amount", _rupees(amount), False),
            ("GST", "Not applicable", False),
        ]
    for label, value, _bold in money_rows:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 8.5)
        c.drawString(14 * mm, y, label)
        c.setFillColor(INK)
        c.drawRightString(W - 14 * mm, y, value)
        y -= 5.6 * mm

    y -= 1 * mm
    c.line(14 * mm, y, W - 14 * mm, y)
    y -= 8 * mm
    c.setFillColor(accent_color)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(14 * mm, y, "Total paid")
    c.drawRightString(W - 14 * mm, y, _rupees(amount))

    # ---- Footer ----
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 6.8)
    c.drawCentredString(W / 2, 16 * mm, "This is a computer generated invoice and does not require a signature.")
    c.drawCentredString(W / 2, 12 * mm, f"Powered by Writtly  |  {library_name}")

    c.showPage()
    c.save()
    return buf.getvalue()
