#!/usr/bin/env python3
"""Multi-tenant SMTP sender.

For every active client in clients/, find the newest newsletter_*.docx in the
private repo's output/<slug>/ directory, email it to that client's recipient,
and record the send in clients/<slug>/.sent_log so retries are idempotent.

Run from cron every 15 minutes; the script is a no-op when nothing new has landed.
"""

from __future__ import annotations

import os
import smtplib
import subprocess
import sys
from datetime import datetime, time as dtime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent
CLIENTS_DIR = ROOT / "clients"
PRIVATE_REPO = ROOT / "pentest"  # historical name; this is the private data repo working tree
APP_PASSWORD_FILE = Path.home() / ".config" / "gmail-app-password"
SERVICE_SENDER = os.environ.get("SERVICE_SENDER", "jacoblarue7@gmail.com")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def log(msg: str) -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def pull_private_repo() -> None:
    if not PRIVATE_REPO.exists():
        raise SystemExit(f"FATAL: private repo not at {PRIVATE_REPO}")
    subprocess.run(
        ["git", "-C", str(PRIVATE_REPO), "pull", "--ff-only"],
        check=True,
    )


def load_clients() -> list[dict]:
    """Return list of {slug, cfg, output_dir, sent_log} for active clients."""
    out: list[dict] = []
    if not CLIENTS_DIR.exists():
        return out
    for client_dir in sorted(CLIENTS_DIR.iterdir()):
        cfg_path = client_dir / "config.yaml"
        if not cfg_path.exists():
            continue
        cfg = yaml.safe_load(cfg_path.read_text())
        if cfg.get("billing", {}).get("status") not in (None, "active"):
            continue  # paused/cancelled
        slug = cfg["client"]["slug"]
        out.append({
            "slug": slug,
            "cfg": cfg,
            "output_dir": PRIVATE_REPO / "output" / slug,
            "sent_log": client_dir / ".sent_log",
        })
    return out


def is_send_window(cfg: dict) -> bool:
    """True if the current local time (in the client's timezone) is at or past
    the configured send time today. Cron fires every 15 min; this guards against
    sending on the wrong day at the wrong hour."""
    sched = cfg.get("schedule", {})
    tz_name = sched.get("timezone", "America/Chicago")
    send_str = sched.get("local_send_local_time") or sched.get("send_local_time", "01:30")
    hh, mm = (int(x) for x in send_str.split(":"))
    now = datetime.now(ZoneInfo(tz_name))
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    # Send any time at or after target on the same calendar day.
    return now >= target and now.date() == target.date()


def send_one(client: dict, password: str) -> bool:
    slug = client["slug"]
    cfg = client["cfg"]

    docs = sorted(client["output_dir"].glob("newsletter_*.docx")) if client["output_dir"].exists() else []
    if not docs:
        log(f"[{slug}] no newsletter in {client['output_dir']}, skipping")
        return False
    latest = docs[-1]

    sent: set[str] = set()
    if client["sent_log"].exists():
        sent = {ln.strip() for ln in client["sent_log"].read_text().splitlines() if ln.strip()}
    if latest.name in sent:
        return False

    if not is_send_window(cfg):
        log(f"[{slug}] {latest.name} ready, but outside send window — will fire next cron tick at/after configured time")
        return False

    recipient = cfg["client"]["recipient_email"]
    title = cfg["newsletter"]["title"]
    date_part = latest.stem.replace("newsletter_", "")

    msg = EmailMessage()
    msg["From"] = f"{title.title()} <{SERVICE_SENDER}>"
    msg["To"] = recipient
    msg["Subject"] = f"{title.title()} — {date_part}"
    msg.set_content(
        f"Your weekly newsletter is attached.\n\nFile: {latest.name}\n"
        f"Generated automatically.\n"
    )
    with latest.open("rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=latest.name,
        )

    log(f"[{slug}] sending {latest.name} to {recipient}")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=60) as smtp:
        smtp.starttls()
        smtp.login(SERVICE_SENDER, password)
        smtp.send_message(msg)

    with client["sent_log"].open("a") as f:
        f.write(latest.name + "\n")
    log(f"[{slug}] sent OK")
    return True


def main() -> int:
    if not APP_PASSWORD_FILE.exists():
        log(f"FATAL: {APP_PASSWORD_FILE} missing")
        return 1
    password = APP_PASSWORD_FILE.read_text().strip()

    pull_private_repo()
    clients = load_clients()
    if not clients:
        log("no active clients; nothing to do")
        return 0

    sent_count = 0
    for client in clients:
        try:
            if send_one(client, password):
                sent_count += 1
        except Exception as e:
            log(f"[{client['slug']}] ERROR: {e}")
    log(f"done — {sent_count} newsletter(s) sent across {len(clients)} client(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
