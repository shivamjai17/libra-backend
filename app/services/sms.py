"""Twilio SMS delivery for Writtly.

Credentials come ONLY from environment/settings — never hardcode them.
Sending is best-effort: failures are logged, never raised, so enrolment and
payment flows are never blocked by an SMS problem.
"""
import logging
import re

from app.core.config import settings

logger = logging.getLogger(__name__)


def normalize_number(raw: str | None) -> str | None:
    """Best-effort E.164 normalization (e.g. '90000 11111' -> '+919000011111')."""
    if not raw:
        return None
    s = re.sub(r"[^\d+]", "", raw)  # strip spaces, dashes, etc.
    if not s:
        return None
    if s.startswith("+"):
        return s
    if s.startswith("00"):
        return "+" + s[2:]
    # bare local number -> prefix default country code
    cc = settings.sms_default_country_code or "+91"
    if len(s) == 10:
        return f"{cc}{s}"
    return f"+{s}"


def send_sms(to_number: str | None, body: str) -> str | None:
    """Send an SMS via Twilio. Returns the message SID, or None if skipped/failed."""
    if not settings.sms_enabled:
        logger.info("SMS disabled; skipping message to %s", to_number)
        return None
    if not settings.sms_configured:
        logger.warning("Twilio not configured (missing SID/token/from); SMS not sent to %s", to_number)
        return None

    to = normalize_number(to_number)
    if not to:
        logger.warning("No valid phone number to send SMS to (got %r)", to_number)
        return None

    try:
        from twilio.rest import Client  # imported lazily so the app runs without twilio installed

        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        message = client.messages.create(to=to, from_=settings.twilio_from_number, body=body)
        logger.info("SMS sent to %s (sid=%s)", to, message.sid)
        return message.sid
    except Exception as exc:  # noqa: BLE001 — never let SMS break the caller
        logger.error("Failed to send Twilio SMS to %s: %s", to, exc)
        return None
