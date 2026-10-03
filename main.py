"""GV-Pulse: keep Google Voice numbers alive by texting them via the Gmail SMTP gateway.

Required env vars:
    GMAIL_USER      Gmail address used to send
    GMAIL_PASSWORD  Gmail App Password (16 chars)
    GV_GATEWAYS     Comma-separated <number>@txt.voice.google.com addresses

Exit code is 0 if every send succeeded, 1 otherwise.
"""

import logging
import os
import random
import re
import smtplib
import sys
import time
from datetime import datetime
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from zoneinfo import ZoneInfo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%m-%d-%Y %I:%M:%S %p",
)
log = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_TIMEOUT = 30  # seconds; don't hang forever on a stalled connection
MAX_RETRIES = 5
BASE_BACKOFF = 5   # seconds; doubles each retry
MAX_BACKOFF = 60
TIMEZONE = ZoneInfo("America/New_York")

MESSAGES = (
    "Update: System is running smoothly.",
    "Reminder: Keep active and stay connected.",
    "Monthly check-in: Hello world!",
    "Status: All systems go.",
    "Ping: Keeping your number alive.",
    "Heartbeat: Everything checks out fine.",
    "Notice: Routine activity confirmation.",
    "Check: This line is still in service.",
    "Log: Scheduled activity ping sent.",
    "Alert: No action needed, just staying active.",
    "Sync: Connection verified and stable.",
)


def mask(address: str) -> str:
    """Hide most of a gateway address so phone numbers don't land in public CI logs."""
    local, _, domain = address.partition("@")
    return f"***{local[-4:]}@{domain}"


def redact(value: object, addresses: list[str]) -> str:
    """
    Stringify *value* (e.g. an SMTP reason or exception) with every gateway
    address, and its bare phone number, masked. Servers can echo the recipient
    back in error text, which would otherwise leak into public CI logs.
    """
    text = value.decode(errors="replace") if isinstance(value, bytes) else str(value)
    for addr in addresses:
        local = addr.partition("@")[0]
        text = re.sub(re.escape(addr), lambda _, a=addr: mask(a), text, flags=re.IGNORECASE)
        if local:
            text = re.sub(re.escape(local), lambda _, n=local: f"***{n[-4:]}", text)
    return text


def parse_gateways(raw: str) -> list[str]:
    """Split a comma-separated list, dropping blanks and duplicates, keeping order."""
    return list(dict.fromkeys(addr.strip() for addr in raw.split(",") if addr.strip()))


def build_message(sender: str, recipient: str) -> EmailMessage:
    """Compose the keep-alive SMS payload."""
    now = datetime.now(TIMEZONE)
    msg = EmailMessage()
    msg["Subject"] = "GV Ping"
    msg["From"] = sender
    msg["To"] = recipient
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=sender.rpartition("@")[2] or None)
    msg.set_content(f"{random.choice(MESSAGES)} | {now:%m-%d-%Y %I:%M %p %Z}")
    return msg


def backoff_delay(attempt: int) -> float:
    """Exponential backoff (capped) plus jitter so retries don't run in lockstep."""
    return min(BASE_BACKOFF * 2 ** (attempt - 1), MAX_BACKOFF) + random.uniform(0, 1)


def send_all(username: str, password: str, recipients: list[str]) -> list[str]:
    """
    Send a keep-alive to every recipient over one authenticated SMTP session,
    reconnecting (and resending only what's left) if the session drops.

    Returns the recipients that were NOT delivered; empty means full success.
    """
    pending = list(recipients)
    sent: set[str] = set()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT) as server:
                server.login(username, password)
                for recipient in pending.copy():
                    try:
                        server.send_message(build_message(username, recipient))
                    except smtplib.SMTPRecipientsRefused as exc:
                        # exc.recipients is keyed by the raw address; use only code + reason.
                        code, reason = next(iter(exc.recipients.values()))
                        reason = redact(reason, recipients)
                        if code >= 500:
                            log.error("%s permanently rejected: %s %s",
                                      mask(recipient), code, reason)
                            pending.remove(recipient)  # retrying can't help
                            continue
                        log.warning("%s refused on attempt %d/%d: %s %s",
                                    mask(recipient), attempt, MAX_RETRIES, code, reason)
                    except smtplib.SMTPServerDisconnected:
                        raise  # session is dead; reconnect instead of failing every remaining send
                    except smtplib.SMTPException as exc:
                        log.warning("Send to %s failed on attempt %d/%d: %s",
                                    mask(recipient), attempt, MAX_RETRIES,
                                    redact(exc, recipients))
                    else:
                        log.info("Sent to %s (attempt %d)", mask(recipient), attempt)
                        pending.remove(recipient)
                        sent.add(recipient)
        except smtplib.SMTPAuthenticationError:
            log.error("Authentication failed — check GMAIL_USER / GMAIL_PASSWORD.")
            break  # retrying a credential error is pointless
        except (smtplib.SMTPException, OSError) as exc:
            log.warning("Connection error on attempt %d/%d: %s",
                        attempt, MAX_RETRIES, redact(exc, recipients))

        if not pending:
            break
        if attempt < MAX_RETRIES:
            delay = backoff_delay(attempt)
            log.info("Retrying %d recipient(s) in %.1fs…", len(pending), delay)
            time.sleep(delay)

    return [r for r in recipients if r not in sent]


def main() -> int:
    username = os.environ.get("GMAIL_USER", "").strip()
    password = os.environ.get("GMAIL_PASSWORD", "").strip()
    if not username or not password:
        log.error("GMAIL_USER and GMAIL_PASSWORD must be set.")
        return 1

    recipients = parse_gateways(os.environ.get("GV_GATEWAYS", ""))
    if not recipients:
        log.error("No gateway configured. Set GV_GATEWAYS (comma-separated).")
        return 1

    log.info("Sending keep-alive to %d gateway(s)…", len(recipients))
    failed = send_all(username, password, recipients)

    if failed:
        log.error("%d/%d sends failed: %s",
                  len(failed), len(recipients), ", ".join(map(mask, failed)))
        return 1

    log.info("All %d send(s) successful.", len(recipients))
    return 0


if __name__ == "__main__":
    sys.exit(main())
