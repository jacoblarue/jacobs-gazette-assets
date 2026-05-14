#!/usr/bin/env python3
"""Render dispatcher — fires local renders when a client's window arrives.

Cron: */15 * * * *

Algorithm per tick:
  For each active client in clients/:
    - Compute their render UTC datetime for today:
        render_time = today's send_time (in client TZ) - render_buffer_minutes
    - If "now" is within (render_time - tolerance, render_time + tolerance]
      AND today's date-slug is NOT in clients/<slug>/.render_log
      AND no render is in progress (clients/<slug>/.render_lock missing):
      fire render_local.sh <slug> as a detached subprocess.

The 15-minute cron tick + a 15-minute tolerance window catch any single firing.
The .render_log is the source of truth for "this customer rendered today" so
duplicate dispatcher ticks within the window are no-ops. Lock prevents
concurrent renders for the same client (paranoia; should never trigger).

Concurrency note: this dispatcher does NOT enforce the 5-hour cross-client
rate-limit constraint at runtime — that is enforced at provisioning by
assign_slot.py. The dispatcher trusts that no two clients have render times
within 5 hours of each other.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent
CLIENTS_DIR = ROOT / "clients"
RENDER_LOCAL = ROOT / "render_local.sh"
DEFAULT_RENDER_BUFFER_MIN = 90  # render must finish this far before send time
TOLERANCE_MIN = 15  # +/- window around render_time considered "now"


def log(msg: str) -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def render_time_today_utc(cfg: dict, now_utc: datetime) -> datetime:
    """Compute today's render-start UTC datetime for a client.

    Render time = (today's send_time in client TZ) - render_buffer_minutes,
    converted to UTC.
    """
    sched = cfg.get("schedule", {})
    tz = ZoneInfo(sched.get("timezone", "America/Chicago"))
    send_str = sched.get("local_send_local_time") or sched.get("send_local_time", "01:30")
    hh, mm = (int(x) for x in send_str.split(":"))
    buffer_min = int(sched.get("render_buffer_minutes", DEFAULT_RENDER_BUFFER_MIN))

    # Anchor "today" in the client's timezone, then walk back the buffer.
    now_local = now_utc.astimezone(tz)
    send_local = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
    render_local = send_local - timedelta(minutes=buffer_min)
    return render_local.astimezone(ZoneInfo("UTC"))


def in_render_window(render_time_utc: datetime, now_utc: datetime) -> bool:
    return abs((now_utc - render_time_utc).total_seconds()) <= TOLERANCE_MIN * 60


def render_log_contains_today(client_dir: Path, date_slug: str) -> bool:
    log_path = client_dir / ".render_log"
    if not log_path.exists():
        return False
    return date_slug in log_path.read_text().splitlines()


def is_render_day(cfg: dict, now_utc: datetime) -> bool:
    """Optional weekly gate: a client's config can specify schedule.render_day
    (mon/tue/wed/...). If unset, we infer from the cloud_cron_utc field."""
    sched = cfg.get("schedule", {})
    target_day = sched.get("render_day")
    if not target_day:
        # Fall back to the cron expression's weekday field
        cron = sched.get("cloud_cron_utc", "")
        parts = cron.split()
        if len(parts) == 5:
            try:
                # cron weekday: 0=Sunday or 7=Sunday, 1=Monday, ...
                cw = int(parts[4])
                target_day = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"][cw % 7]
            except ValueError:
                return True  # malformed cron, don't gate
        else:
            return True
    weekday_name = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][now_utc.weekday()]
    return weekday_name == target_day.lower()[:3]


def main() -> int:
    if not CLIENTS_DIR.exists():
        log("no clients dir; nothing to do")
        return 0

    now_utc = datetime.now(ZoneInfo("UTC"))
    fired = 0

    for client_dir in sorted(CLIENTS_DIR.iterdir()):
        cfg_path = client_dir / "config.yaml"
        if not cfg_path.exists():
            continue
        cfg = yaml.safe_load(cfg_path.read_text())
        if cfg.get("billing", {}).get("status") not in (None, "active"):
            continue
        slug = cfg["client"]["slug"]

        if not is_render_day(cfg, now_utc):
            continue

        render_time = render_time_today_utc(cfg, now_utc)
        if not in_render_window(render_time, now_utc):
            continue

        # Use UTC date as slug; matches what render_local.sh writes
        date_slug = now_utc.strftime("%Y-%m-%d")
        if render_log_contains_today(client_dir, date_slug):
            log(f"[{slug}] already rendered for {date_slug}, skipping")
            continue
        lock = client_dir / ".render_lock"
        if lock.exists():
            log(f"[{slug}] render in progress (lock exists), skipping")
            continue

        log(f"[{slug}] firing render — render_time={render_time.isoformat()} now={now_utc.isoformat()}")
        # Detach; we don't wait. The launcher writes to /tmp/jg-render-<slug>-*.log
        subprocess.Popen(
            [str(RENDER_LOCAL), slug],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        fired += 1

    log(f"done — fired {fired} render(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
