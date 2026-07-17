"""File storage for logos and receipts.

Uses S3 when configured; otherwise falls back to local disk under ./media so
development works without AWS. Never raises on upload failure — callers treat
a None return as "no file stored".
"""
import io
import logging
import os
import uuid
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

LOCAL_MEDIA_DIR = Path("media")
ALLOWED_IMAGE_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2 MB
LOGO_MAX_PX = 512


def _s3_client():
    import boto3

    return boto3.client("s3", region_name=settings.s3_region)


def _public_url(key: str) -> str:
    if settings.s3_public_base_url:
        return f"{settings.s3_public_base_url.rstrip('/')}/{key}"
    return f"https://{settings.s3_bucket}.s3.{settings.s3_region}.amazonaws.com/{key}"


def put_bytes(key: str, data: bytes, content_type: str) -> str | None:
    """Store bytes and return a public URL (or None on failure)."""
    if settings.s3_configured:
        try:
            _s3_client().put_object(
                Bucket=settings.s3_bucket, Key=key, Body=data,
                ContentType=content_type, CacheControl="public,max-age=31536000",
            )
            return _public_url(key)
        except Exception as exc:  # noqa: BLE001
            logger.error("S3 upload failed for %s: %s", key, exc)
            return None

    # Local fallback (development).
    try:
        path = LOCAL_MEDIA_DIR / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"{settings.public_base_url.rstrip('/')}/media/{key}"
    except Exception as exc:  # noqa: BLE001
        logger.error("Local storage failed for %s: %s", key, exc)
        return None


def get_bytes(key: str) -> bytes | None:
    """Read a stored file back (used to embed the logo into PDFs)."""
    if settings.s3_configured:
        try:
            obj = _s3_client().get_object(Bucket=settings.s3_bucket, Key=key)
            return obj["Body"].read()
        except Exception as exc:  # noqa: BLE001
            logger.warning("S3 read failed for %s: %s", key, exc)
            return None
    try:
        return (LOCAL_MEDIA_DIR / key).read_bytes()
    except Exception:  # noqa: BLE001
        return None


def key_from_url(url: str | None) -> str | None:
    """Recover the storage key from a URL produced by put_bytes()."""
    if not url:
        return None
    for marker in ("/logos/", "/receipts/"):
        if marker in url:
            return url.split("/", 3)[-1] if url.startswith("http") and marker not in url[:8] else url[url.index(marker) + 1:]
    return None


def process_logo(raw: bytes, content_type: str, library_id: str) -> tuple[str | None, str | None]:
    """Validate + downscale a logo, store it, return (url, error)."""
    if content_type not in ALLOWED_IMAGE_TYPES:
        return None, "Logo must be a PNG, JPG or WEBP image"
    if len(raw) > MAX_LOGO_BYTES:
        return None, "Logo must be under 2 MB"

    try:
        from PIL import Image

        img = Image.open(io.BytesIO(raw))
        img = img.convert("RGBA") if img.mode in ("P", "LA", "RGBA") else img.convert("RGB")
        img.thumbnail((LOGO_MAX_PX, LOGO_MAX_PX))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data = buf.getvalue()
    except Exception as exc:  # noqa: BLE001
        logger.error("Logo processing failed: %s", exc)
        return None, "Could not read that image"

    key = f"logos/{library_id}/{uuid.uuid4().hex[:12]}.png"
    url = put_bytes(key, data, "image/png")
    if not url:
        return None, "Could not store the logo. Please try again."
    return url, None


def store_receipt(pdf: bytes, library_id: str, payment_id: str) -> str | None:
    key = f"receipts/{library_id}/{payment_id}.pdf"
    return put_bytes(key, pdf, "application/pdf")
