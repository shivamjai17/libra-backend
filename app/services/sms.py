"""Twilio SMS delivery for Writtly.

Credentials come ONLY from environment/settings — never hardcode them.
Sending is best-effort: failures are logged and returned, never raised, so
enrolment and payment flows are never blocked by an SMS problem.
"""
import logging
import re

from app.core.config import settings

logger = logging.getLogger(__name__)


def normalize_number(raw: str | None) -> str | None:
    """Best-effort E.164 normalization. Accepts numbers WITH or WITHOUT a
    country code:
        '9000011111'        -> '+919000011111'   (10-digit -> default CC)
        '09000011111'       -> '+919000011111'   (drops leading 0)
        '919000011111'      -> '+919000011111'   (already has 91)
        '+91 90000 11111'   -> '+919000011111'
        '0091 9000011111'   -> '+919000011111'
    """
    if not raw:
        return None
    s = re.sub(r"[^\d+]", "", raw)  # strip spaces, dashes, brackets
    if not s:
        return None
    if s.startswith("+"):
        return s
    if s.startswith("00"):          # international prefix 00 -> +
        s = s[2:]
        return "+" + s if s else None

    cc = (settings.sms_default_country_code or "+91").strip()
    cc_digits = cc.lstrip("+")

    s = s.lstrip("0")               # drop domestic trunk zero(s)
    if len(s) == 10:               # bare local number -> add country code
        return f"{cc}{s}"
    if s.startswith(cc_digits) and len(s) == len(cc_digits) + 10:
        return f"+{s}"             # already includes the country code
    return f"+{s}"                 # fallback: assume it's already international


def send_sms_result(to_number: str | None, body: str) -> dict:
    """Send an SMS and return a detailed result dict (never raises)."""
    if not settings.sms_enabled:
        return {"ok": False, "skipped": "sms_disabled", "to": to_number}
    if not settings.sms_configured:
        return {"ok": False, "skipped": "not_configured",
                "detail": "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER in .env",
                "to": to_number}

    to = normalize_number(to_number)
    if not to:
        return {"ok": False, "error": "invalid_number", "to": to_number}

    try:
        from twilio.rest import Client  # lazy import so the app runs without twilio installed

        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        message = client.messages.create(to=to, from_=settings.twilio_from_number, body=body)
        logger.info("SMS sent to %s (sid=%s)", to, message.sid)
        return {"ok": True, "sid": message.sid, "to": to}
    except Exception as exc:  # noqa: BLE001 — never let SMS break the caller
        logger.error("Failed to send Twilio SMS to %s: %s", to, exc)
        return {"ok": False, "error": str(exc), "to": to}


def send_sms(to_number: str | None, body: str) -> str | None:
    """Convenience wrapper: returns the message SID, or None if skipped/failed."""
    return send_sms_result(to_number, body).get("sid")
