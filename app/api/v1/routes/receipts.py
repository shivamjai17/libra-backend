"""Public receipt links: /r/{token} -> the stored PDF.

Deliberately unauthenticated (students receive the link by SMS) but
unguessable: tokens are random and map to exactly one payment.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.operations import Payment

router = APIRouter(tags=["receipts"])


@router.get("/r/{token}", include_in_schema=False)
async def receipt_redirect(token: str, db: AsyncSession = Depends(get_db)):
    payment = (await db.execute(
        select(Payment).where(Payment.receipt_token == token)
    )).scalar_one_or_none()
    if payment is None or not payment.receipt_url:
        raise HTTPException(404, "Receipt not found")
    return RedirectResponse(payment.receipt_url, status_code=302)
