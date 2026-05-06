#!/usr/bin/env bash
# Cron wrapper: pulls private repo, sends latest newsletter via Gmail SMTP.
# System TZ is America/Chicago — cron interprets times in local time directly.
# Schedule (add to `crontab -e`):
#   30 1 * * 1 /home/reddiamond/jacobs-gazette/local_send.sh
set -euo pipefail
LOG="$HOME/jacobs-gazette/output/send.log"
mkdir -p "$(dirname "$LOG")"
{
  echo "=== run $(date -Is) ==="
  python3 "$HOME/jacobs-gazette/local_send.py"
} >>"$LOG" 2>&1
