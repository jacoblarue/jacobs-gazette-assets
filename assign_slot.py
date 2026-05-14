#!/usr/bin/env python3
"""Validate a client's render slot against the 5-hour rate-limit constraint.

Run at provisioning, after editing the new client's config.yaml. Exits 0 if
the slot is clear; exits 1 with suggestions if it conflicts with an existing
client's render time.

Usage: assign_slot.py <client_slug>

A render "slot" is the UTC time-of-day-of-week when that client's render starts.
Two slots conflict iff they fall on the same weekday AND their UTC times are
fewer than 5 hours apart. Different weekdays never conflict (Anthropic's rate
limit is a 5-hour rolling window).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent
CLIENTS_DIR = ROOT / "clients"
SPACING_HOURS = 5

WEEKDAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def render_slot(cfg: dict) -> tuple[str, int]:
    """Return (weekday_short, render_minute_of_day_utc) for a client config.

    Computes the render START time as today's send time minus render_buffer_minutes,
    expressed in UTC. The actual date doesn't matter; we only care about the
    weekday + time-of-day for spacing.
    """
    sched = cfg.get("schedule", {})
    tz = ZoneInfo(sched.get("timezone", "America/Chicago"))
    send_str = sched.get("local_send_local_time") or sched.get("send_local_time", "01:30")
    hh, mm = (int(x) for x in send_str.split(":"))
    buffer_min = int(sched.get("render_buffer_minutes", 90))

    # Pick any reference week; weekday math is stable.
    ref = datetime(2026, 5, 4, hh, mm, tzinfo=tz)  # Monday 2026-05-04
    cron = sched.get("cloud_cron_utc", "")
    parts = cron.split()
    if len(parts) == 5:
        try:
            cron_weekday = int(parts[4]) % 7
            # cron 0/7=Sun, 1=Mon, 2=Tue...
            offset = (cron_weekday - 1) % 7  # to Mon-indexed (Mon=0)
            ref = ref + timedelta(days=offset)
        except ValueError:
            pass
    render_local = ref - timedelta(minutes=buffer_min)
    render_utc = render_local.astimezone(ZoneInfo("UTC"))
    weekday = WEEKDAY_NAMES[render_utc.weekday()]
    minute_of_day = render_utc.hour * 60 + render_utc.minute
    return weekday, minute_of_day


def fmt_minute(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: assign_slot.py <client_slug>", file=sys.stderr)
        return 2
    new_slug = sys.argv[1]
    new_cfg_path = CLIENTS_DIR / new_slug / "config.yaml"
    if not new_cfg_path.exists():
        print(f"ERROR: {new_cfg_path} not found", file=sys.stderr)
        return 2

    new_cfg = yaml.safe_load(new_cfg_path.read_text())
    new_day, new_minute = render_slot(new_cfg)

    conflicts: list[tuple[str, str, int]] = []
    same_day_existing: list[tuple[str, int]] = []
    for client_dir in sorted(CLIENTS_DIR.iterdir()):
        if client_dir.name == new_slug:
            continue
        cfg_path = client_dir / "config.yaml"
        if not cfg_path.exists():
            continue
        cfg = yaml.safe_load(cfg_path.read_text())
        if cfg.get("billing", {}).get("status") == "cancelled":
            continue
        ex_day, ex_minute = render_slot(cfg)
        if ex_day != new_day:
            continue
        same_day_existing.append((client_dir.name, ex_minute))
        delta = abs(ex_minute - new_minute)
        # Account for cross-midnight (e.g. 23:30 vs 02:30 = 3hr apart, not 21hr)
        delta = min(delta, 24 * 60 - delta)
        if delta < SPACING_HOURS * 60:
            conflicts.append((client_dir.name, ex_day, ex_minute))

    print(f"\nProposed render slot for {new_slug}:  {new_day} {fmt_minute(new_minute)} UTC")
    print(f"  (derived from local_send_local_time={new_cfg['schedule'].get('local_send_local_time')} "
          f"in {new_cfg['schedule'].get('timezone')}, "
          f"render_buffer_minutes={new_cfg['schedule'].get('render_buffer_minutes', 90)})\n")

    if not conflicts:
        if same_day_existing:
            print("Same-day existing slots (none within 5 hr):")
            for s, m in same_day_existing:
                print(f"  {s}: {fmt_minute(m)} UTC")
        print(f"\nOK — slot is clear (≥{SPACING_HOURS}h from every existing same-day render).")
        return 0

    print(f"CONFLICT — proposed slot is within {SPACING_HOURS}h of existing render(s):")
    for slug, day, minute in conflicts:
        delta = min(abs(minute - new_minute), 24*60 - abs(minute - new_minute))
        print(f"  {slug}: {day} {fmt_minute(minute)} UTC  (Δ {delta // 60}h{delta % 60:02d}m)")

    print("\nSuggestions to resolve:")
    print(f"  • Move {new_slug}'s send time earlier or later by enough hours to clear the window")
    print(f"  • Or change {new_slug}'s render day (edit cloud_cron_utc weekday field)")
    print(f"  • Or shift one of the conflicting clients (their config too)")
    print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
