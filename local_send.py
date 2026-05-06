#!/usr/bin/env python3
"""Local SMTP fallback sender for Jacob's Gazette.

Pulls the private repo, finds the newest newsletter_<date>.docx in output/,
emails it to the recipient via Gmail SMTP (smtplib + app password), and
records the send in .sent_log to stay idempotent across cron retries.
"""

import smtplib
import subprocess
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

PRIVATE_REPO = Path.home() / "jacobs-gazette" / "pentest"
SENT_LOG = Path.home() / "jacobs-gazette" / ".sent_log"
APP_PASSWORD_FILE = Path.home() / ".config" / "gmail-app-password"
RECIPIENT = "jacoblarue7@gmail.com"
SENDER = "jacoblarue7@gmail.com"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def log(msg: str) -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def main() -> int:
    if not PRIVATE_REPO.exists():
        log(f"FATAL: {PRIVATE_REPO} does not exist; clone the private repo first")
        return 1
    if not APP_PASSWORD_FILE.exists():
        log(f"FATAL: {APP_PASSWORD_FILE} missing")
        return 1

    log(f"git pull in {PRIVATE_REPO}")
    subprocess.run(
        ["git", "-C", str(PRIVATE_REPO), "pull", "--ff-only"],
        check=True,
    )

    output_dir = PRIVATE_REPO / "output"
    docs = sorted(output_dir.glob("newsletter_*.docx"))
    if not docs:
        log(f"FATAL: no newsletter_*.docx in {output_dir}")
        return 1
    latest = docs[-1]
    log(f"latest newsletter: {latest.name}")

    sent = set()
    if SENT_LOG.exists():
        sent = {line.strip() for line in SENT_LOG.read_text().splitlines() if line.strip()}
    if latest.name in sent:
        log(f"already sent {latest.name}, nothing to do")
        return 0

    password = APP_PASSWORD_FILE.read_text().strip()

    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    date_part = latest.stem.replace("newsletter_", "")
    msg["Subject"] = f"Jacob's Gazette — {date_part}"
    msg.set_content(
        "Your weekly newsletter is attached.\n"
        f"\nFile: {latest.name}\n"
        "Generated automatically by jacobs-gazette.\n"
    )
    with latest.open("rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=latest.name,
        )

    log(f"connecting to {SMTP_HOST}:{SMTP_PORT}")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=60) as smtp:
        smtp.starttls()
        smtp.login(SENDER, password)
        smtp.send_message(msg)
    log(f"sent {latest.name} to {RECIPIENT}")

    with SENT_LOG.open("a") as f:
        f.write(latest.name + "\n")
    log(f"appended {latest.name} to {SENT_LOG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
