import smtplib
import os
import random
import sys
import time
import logging
from email.mime.text import MIMEText
from email.utils import make_msgid, formatdate
from datetime import datetime
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%m-%d-%Y %I:%M:%S %p",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_TIMEOUT = 30          # seconds — avoid hanging forever on a stalled connection
MAX_RETRIES = 5
BASE_BACKOFF = 5           # seconds — doubles each retry, capped below
MAX_BACKOFF = 60

MESSAGES = [
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
]


def build_message(sender: str, recipient: str) -> MIMEText:
    """Compose the keep-alive SMS payload."""
    now = datetime.now(ZoneInfo("America/New_York"))
    body = (
        f"{random.choice(MESSAGES)} | "
        f"{now.strftime('%m-%d-%Y %I:%M %p %Z')}"
    )
    msg = MIMEText(body)
    msg["Subject"] = "GV Ping"
    msg["From"] = sender
    msg["To"] = recipient
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    return msg


def send_all(username: str, password: str, recipients: list[str]) -> list[bool]:
    """
    Send a keep-alive message to every recipient, reusing a single
    authenticated SMTP session where possible. Falls back to reconnecting
    if the session drops mid-run.

    Returns a list of per-recipient success flags, in the same order as
    *recipients*.
    """
    results = [False] * len(recipients)
    pending = list(enumerate(recipients))  # (index, recipient) pairs left to send

    for attempt in range(1, MAX_RETRIES + 1):
        if not pending:
            break

        still_pending = []
        try:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT) as server:
                server.login(username, password)
                for idx, recipient in pending:
                    msg = build_message(username, recipient)
                    try:
                        server.sendmail(username, [recipient], msg.as_string())
                        log.info("Sent to %s (attempt %d)", recipient, attempt)
                        results[idx] = True
                    except smtplib.SMTPException as exc:
                        log.warning(
                            "Send to %s failed on attempt %d/%d: %s",
                            recipient, attempt, MAX_RETRIES, exc,
                        )
                        still_pending.append((idx, recipient))
        except smtplib.SMTPAuthenticationError:
            log.error("Authentication failed — check GMAIL_USER / GMAIL_PASSWORD.")
            return results  # No point retrying a credential error
        except (smtplib.SMTPException, OSError) as exc:
            log.warning(
                "Connection error on attempt %d/%d: %s", attempt, MAX_RETRIES, exc
            )
            still_pending = pending  # nothing got sent this round

        pending = still_pending
        if pending and attempt < MAX_RETRIES:
            backoff = min(BASE_BACKOFF * (2 ** (attempt - 1)), MAX_BACKOFF)
            backoff += random.uniform(0, 1)  # small jitter to avoid lockstep retries
            log.info("Retrying %d recipient(s) in %.1fs…", len(pending), backoff)
            time.sleep(backoff)

    for idx, recipient in pending:
        log.error("All %d attempts failed for %s", MAX_RETRIES, recipient)

    return results


def main() -> int:
    """
    Entry point.  Reads credentials from environment variables and sends a
    keep-alive message to every configured GV gateway.

    Required env vars:
        GMAIL_USER      – Gmail address used to send
        GMAIL_PASSWORD  – Gmail App Password (16 chars)

    Gateway env vars (at least one required):
        GV_GATEWAYS     – comma-separated list of @txt.voice.google.com
                           addresses, e.g. "5551234567@txt.voice.google.com,..."

    Returns exit code 0 on full success, 1 if any send failed.
    """
    username = os.environ.get("GMAIL_USER", "").strip()
    password = os.environ.get("GMAIL_PASSWORD", "").strip()

    if not username or not password:
        log.error("GMAIL_USER and GMAIL_PASSWORD must be set.")
        return 1

    # Collect all configured gateways from every supported source, skipping
    # blanks, and de-duping while preserving order.
    raw = os.environ.get("GV_GATEWAYS", "").split(",")

    seen = set()
    recipients = []
    for entry in raw:
        addr = entry.strip()
        if addr and addr not in seen:
            seen.add(addr)
            recipients.append(addr)

    if not recipients:
        log.error(
            "No gateway configured. Set GV_GATEWAYS (comma-separated)"
        )
        return 1

    log.info("Sending keep-alive to %d gateway(s)…", len(recipients))
    results = send_all(username, password, recipients)

    failures = results.count(False)
    if failures:
        log.error("%d/%d sends failed.", failures, len(results))
        return 1

    log.info("All %d send(s) successful.", len(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
