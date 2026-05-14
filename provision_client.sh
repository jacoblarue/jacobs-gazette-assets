#!/usr/bin/env bash
# Onboard a new newsletter client.
#
# Usage: ./provision_client.sh <slug> <recipient_email> [template_slug]
#   slug             Filesystem-safe client name (one word, lowercase). Becomes clients/<slug>/.
#   recipient_email  Where the newsletter ships every week.
#   template_slug    Existing client to copy config from (default: jacob).
#
# This sets up the local directory structure and writes a starter config.yaml.
# It does NOT create the cloud routine — that has to be done from a Claude
# session via RemoteTrigger. Steps printed at the end.

set -euo pipefail

SLUG="${1:-}"
RECIPIENT="${2:-}"
TEMPLATE="${3:-jacob}"

if [[ -z "$SLUG" || -z "$RECIPIENT" ]]; then
  echo "Usage: $0 <slug> <recipient_email> [template_slug]" >&2
  exit 1
fi
if [[ ! "$SLUG" =~ ^[a-z][a-z0-9_]*$ ]]; then
  echo "ERROR: slug must be lowercase letters/digits/underscores, starting with a letter" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE_DIR="$ROOT/clients/$TEMPLATE"
CLIENT_DIR="$ROOT/clients/$SLUG"

if [[ ! -d "$TEMPLATE_DIR" ]]; then
  echo "ERROR: template client '$TEMPLATE' not found at $TEMPLATE_DIR" >&2
  exit 1
fi
if [[ -e "$CLIENT_DIR" ]]; then
  echo "ERROR: $CLIENT_DIR already exists; refusing to overwrite" >&2
  exit 1
fi

echo "[1/4] Creating $CLIENT_DIR/"
mkdir -p "$CLIENT_DIR/assets"

echo "[2/4] Copying config from template '$TEMPLATE'"
cp "$TEMPLATE_DIR/config.yaml" "$CLIENT_DIR/config.yaml"

echo "[3/4] Patching slug + recipient"
# Use awk so we don't depend on yq. We only swap the two specific values.
python3 - <<PY
import yaml, pathlib
p = pathlib.Path("$CLIENT_DIR/config.yaml")
cfg = yaml.safe_load(p.read_text())
cfg["client"]["slug"] = "$SLUG"
cfg["client"]["recipient_email"] = "$RECIPIENT"
cfg["credentials"]["alpaca_keys"] = "jacobs-gazette/clients/$SLUG/alpaca-keys"
# Reset billing — set monthly price + status manually after Stripe is in place.
cfg.setdefault("billing", {})
cfg["billing"]["monthly_price_usd"] = 0
cfg["billing"]["status"] = "pending"
p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
PY

echo "[4/5] Scaffolding output directory in private repo"
mkdir -p "$ROOT/pentest/output/$SLUG" "$ROOT/pentest/reports/$SLUG"

echo "[5/5] Validating render slot vs. 5-hour rate-limit constraint"
if ! "$ROOT/assign_slot.py" "$SLUG"; then
  cat <<EOM

  ⚠ Render slot conflicts with an existing client. Onboarding NOT complete.
  Edit $CLIENT_DIR/config.yaml — change schedule.local_send_local_time or
  schedule.cloud_cron_utc weekday — and rerun:
       $ROOT/assign_slot.py $SLUG
  until it returns OK. Then proceed with the manual steps below.

EOM
fi

cat <<EOM

  Provisioned clients/$SLUG/
  Config:    $CLIENT_DIR/config.yaml
  Recipient: $RECIPIENT
  Template:  $TEMPLATE

  NEXT STEPS (manual):

  1. EDIT the config to match the client's intake form:
       \$EDITOR $CLIENT_DIR/config.yaml
     Pay attention to: newsletter.title, newsletter.tagline, branding.colors,
     location, sections array (which to enable + per-section config blocks).

  2. (Optional) drop a logo PNG at:
       $CLIENT_DIR/assets/header_logo.png
     Renderer falls back to Jacob's logo if missing.

  3. (Optional) drop client-specific Alpaca keys at:
       $CLIENT_DIR/alpaca-keys
     Format: line 1 = key id, line 2 = secret. Required only if alpaca_paper enabled.

  4. NO CLOUD ROUTINE NEEDED — renders run locally on this Kali via render_dispatcher.py
     (cron */15) when the client's window arrives. The window is derived from
     schedule.local_send_local_time in their config.yaml minus render_buffer_minutes
     (default 90). Verify with:
       $ROOT/assign_slot.py $SLUG

  5. SET UP billing in Stripe (Payment Link → subscription). When payment confirms,
     edit billing.status: pending → active in $CLIENT_DIR/config.yaml.

  6. COMMIT the new client config:
       cd $ROOT && git add clients/$SLUG && git commit -m "onboard: $SLUG"
       cd pentest && git add output/$SLUG && git commit -m "scaffold output/ for $SLUG"

EOM
