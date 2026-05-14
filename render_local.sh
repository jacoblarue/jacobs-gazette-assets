#!/usr/bin/env bash
# Launch a local Claude Code render for one client.
# Invoked by render_dispatcher.py when a client's render window arrives.
#
# Usage: render_local.sh <client_slug>
#
# This script:
#   1. Symlinks /tmp/jg → ~/jacobs-gazette and /tmp/jg-private → ~/jacobs-gazette/pentest
#      so agent_prompt.md (which references /tmp paths) operates on local working trees.
#   2. Loads credentials from ~/.config/ and clients/<slug>/.
#   3. Invokes `claude -p` headless with the same prompt the cloud routine uses.
#   4. Cleans up symlinks on exit.
#
# Stdout/stderr go to /tmp/jg-render-<slug>-<iso8601>.log. Acquires/releases
# clients/<slug>/.render_lock to prevent concurrent fires. Appends today's
# date-slug to clients/<slug>/.render_log on success so dispatcher won't re-fire.

set -euo pipefail

SLUG="${1:-}"
if [[ -z "$SLUG" ]]; then
  echo "Usage: $0 <client_slug>" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")" && pwd)"
CLIENT_DIR="$ROOT/clients/$SLUG"
LOCK="$CLIENT_DIR/.render_lock"
LOG="$CLIENT_DIR/.render_log"
DATE_SLUG="$(date -u +%Y-%m-%d)"
RENDER_LOG="/tmp/jg-render-${SLUG}-$(date -u +%Y%m%dT%H%M%SZ).log"

if [[ ! -d "$CLIENT_DIR" ]]; then
  echo "ERROR: no client dir at $CLIENT_DIR" >&2
  exit 1
fi
if [[ -f "$LOCK" ]]; then
  echo "ERROR: render already in progress (lock at $LOCK)" >&2
  exit 1
fi

# Lock + cleanup
trap 'rm -f "$LOCK"; rm -f /tmp/jg /tmp/jg-private' EXIT
echo "$$" > "$LOCK"

# Symlink working trees into /tmp paths the prompt expects
rm -f /tmp/jg /tmp/jg-private
ln -s "$ROOT" /tmp/jg
ln -s "$ROOT/pentest" /tmp/jg-private

# Credentials
export CLIENT_SLUG="$SLUG"
export GH_TOKEN="$(cat ~/.config/gh-pat)"

ALPACA_FILE="$CLIENT_DIR/alpaca-keys"
if [[ ! -f "$ALPACA_FILE" ]]; then
  ALPACA_FILE=~/.config/alpaca-keys
fi
if [[ -f "$ALPACA_FILE" ]]; then
  export ALPACA_KEY_ID="$(sed -n 1p "$ALPACA_FILE")"
  export ALPACA_SECRET_KEY="$(sed -n 2p "$ALPACA_FILE")"
fi

# Build the launch prompt — short bootstrap that hands off to agent_prompt.md
PROMPT="$(cat <<EOF
You are an automated weekly newsletter generator running for client: ${SLUG}.

Environment is already set up. The assets repo is at /tmp/jg (symlinked to the
local working tree) and the private data repo is at /tmp/jg-private. You do
NOT need to clone — Step 0's clone commands are guarded with idempotency
checks and will skip when the trees are already present.

Credentials are exported as env vars: CLIENT_SLUG, GH_TOKEN, ALPACA_KEY_ID,
ALPACA_SECRET_KEY. Read them as Python via os.environ.

Now read /tmp/jg/agent_prompt.md and execute every step in order. The Canva
MCP is NOT available in this environment — use the documented text-only
title-page fallback (omit image_path, set tagline only).

When the render finishes successfully (.docx pushed to the private repo),
exit cleanly. Do not attempt to send email — the local cron does that.
EOF
)"

echo "[$(date -Iseconds)] starting render for $SLUG" | tee -a "$RENDER_LOG"
claude -p "$PROMPT" \
  --allowed-tools "Bash Read Write Edit Glob Grep WebSearch WebFetch" \
  --max-turns 100 \
  --output-format stream-json \
  --verbose \
  >> "$RENDER_LOG" 2>&1

# Verify a docx for today landed
EXPECTED="$ROOT/pentest/output/$SLUG/newsletter_${DATE_SLUG}.docx"
if [[ -f "$EXPECTED" ]]; then
  echo "$DATE_SLUG" >> "$LOG"
  echo "[$(date -Iseconds)] $SLUG render OK — wrote $EXPECTED" | tee -a "$RENDER_LOG"
  exit 0
else
  echo "[$(date -Iseconds)] $SLUG render FAILED — no $EXPECTED" | tee -a "$RENDER_LOG"
  exit 2
fi
