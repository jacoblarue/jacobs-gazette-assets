# Personal Newsletter — Business Plan

**Working name:** TBD ("Jacob's Gazette" is the prototype client; the service itself needs a separate brand).
**Founder:** Jacob LaRue.
**Stack:** Kali Linux home server + GitHub repos + Anthropic cloud routines + Stripe + Gmail SMTP.
**One-line pitch:** A premium weekly Word-document newsletter, fully personalized to each subscriber's interests, delivered to their inbox automatically.

---

## What we sell

A 10–20 page weekly newsletter, formatted as a polished `.docx`, generated each week from up to 18 personalized sections covering the customer's hand-picked topics — industry news, devotional, recipe, vehicle watches, concert/Airbnb scouting, paper-trading snapshot, crossword, etc. Fully automated end-to-end. Customer fills out a one-page intake form once; the newsletter shows up in their inbox at their chosen time every week.

## How it works (architecture — local-render model)

All renders run on the Kali home server through `claude` CLI in headless mode. This means renders consume the operator's flat Pro/Max subscription quota instead of metered Anthropic API spend per render. Capacity ceiling: ~15 customers on Max 5x ($100/mo), ~25 on Max 20x ($200/mo). See "Migration plan" below for the move to RemoteTrigger when scale demands it.

1. **Intake**: customer fills out `CLIENT_INTAKE.md`. We transcribe to `clients/<slug>/config.yaml` via `provision_client.sh`. The script also calls `assign_slot.py <slug>` to verify the proposed render time is ≥5 hours from any other client's slot on the same weekday (Anthropic's rolling rate-limit window).
2. **Render dispatcher** (`render_dispatcher.py`, cron `*/15 * * * *`): every 15 minutes, scans `clients/`, computes each client's render-start UTC time as `local_send_local_time - render_buffer_minutes` (default 90), and fires `render_local.sh <slug>` if the client is in their window AND today's date isn't already in `.render_log`.
3. **Render launcher** (`render_local.sh`): symlinks `/tmp/jg → ~/jacobs-gazette` and `/tmp/jg-private → ~/jacobs-gazette/pentest` so the existing prompt's path expectations work, exports credentials as env vars, invokes `claude -p` headless with the bootstrap prompt that hands off to `agent_prompt.md`. Lock file prevents concurrent fires.
4. **Agent execution**: Claude reads `agent_prompt.md`, gathers all enabled sections via WebSearch/WebFetch + APIs (Alpaca, Strava), runs `render.py --config clients/<slug>/config.yaml`, pushes the `.docx` to the private repo at `output/<slug>/`.
5. **Send dispatcher** (`send.py`, cron `*/15 * * * *`): pulls the private repo, finds any client whose `local_send_local_time` has passed today and whose newest `.docx` isn't yet in `.sent_log`, sends via SMTP from a single service Gmail account.
6. **Idempotency**: `.render_log` (one date-slug per line, "rendered today, don't fire again") and `.sent_log` (filenames already emailed) live in each `clients/<slug>/` directory.

## Constraints the scheduler enforces

- **5-hour rate-limit spacing**: any two clients with the same render weekday must have render-start times ≥5 hours apart. Enforced at provisioning by `assign_slot.py`. Different weekdays don't conflict.
- **Render must finish before send**: `render_buffer_minutes` (default 90) is how much earlier the render starts vs the send time. Tune per-client in their config if a particular newsletter consistently runs long.
- **Operator's interactive Claude usage**: counts against the same Max subscription bucket. Avoid heavy interactive Claude Code work during a customer's render window.

## Files in the multi-tenant build

| File | Purpose |
| --- | --- |
| `render.py` | `.docx` renderer; reads `--config <client.yaml>` for branding (colors, title, tagline, logo) |
| `agent_prompt.md` | Newsletter-generation prompt; parameterized by `CLIENT_SLUG` env var; idempotent Step 0 works for both cloud (clones to `/tmp`) and local (symlinks already in place) |
| `clients/<slug>/config.yaml` | Per-client spec (recipient, schedule, branding, sections, billing status) |
| `clients/<slug>/assets/` | Per-client logo + per-render Canva title pages |
| `clients/<slug>/.render_log` | Idempotency record — date-slugs of completed renders |
| `clients/<slug>/.sent_log` | Idempotency record — filenames of emails already sent |
| `clients/<slug>/.render_lock` | Transient lock during an in-flight render |
| `provision_client.sh` | Onboard a new client: scaffold dirs, copy template config, validate render slot |
| `assign_slot.py` | Verify a client's render time is ≥5h from any same-day existing client |
| `render_dispatcher.py` | Cron-fired (every 15 min); finds clients in their render window, kicks off `render_local.sh` |
| `render_local.sh` | Wraps `claude -p` headless: symlinks paths, exports creds, invokes agent |
| `send.py` | Multi-tenant SMTP sender |
| `CLIENT_INTAKE.md` | Customer-facing intake form |

## Migration plan: local → cloud

When the operator hits ~15 paying customers on Max 5x (or ~25 on Max 20x), or when Anthropic raises a flag about commercial use of the personal subscription, the migration path is:

1. For each paying client, register an Anthropic Remote Trigger with the same `agent_prompt.md` content (the prompt's Step 0 is already idempotent, so it works in both contexts).
2. Disable that client's local render by setting `billing.tier: cloud` in their config (small dispatcher tweak to skip clients on cloud tier).
3. Keep `send.py` cron exactly as-is — cloud routine pushes `.docx` to the same private-repo path the sender expects.
4. Free-tier dry runs and friend-and-family clients stay on local. Paid customers move to API billing.

Effort to migrate: ~30 min per client (one RemoteTrigger.create call + a config flip).

## Pricing

Initial pricing: **$19/mo** (founder pricing for the first 10 customers, then **$29/mo**).

Unit economics per customer per month (4 newsletters):
- Anthropic API render cost: ~$1–3 × 4 = **$4–12/mo**
- Stripe processing: 2.9% + $0.30 = **$0.85/mo**
- Email send: free (under Gmail's 2000/day Workspace cap until ~50 customers)
- Server: $0 marginal (Kali is owned, electricity rounding error)

Gross margin at $19/mo: **~$6–14 per customer per month** (depending on render variance).
Gross margin at $29/mo: **~$16–24**.

Premium tier ($49/mo) when ready: ships a Raspberry Pi to enable the home network security section. Hardware cost ~$60 — recoup in month 2.

## Payment processing

**V1 — manual provisioning, Stripe Payment Links** (set up 2026-05-07 via Stripe MCP):
- Stripe sandbox account: `acct_1TUf7fRr1GKhGy6B` ("Newsletter sandbox")
- Product: `prod_UTcrsWzxJwHpNA` — "Personal Newsletter"
- Price: `price_1TUfc4Rr1GKhGy6B77nWF8dB` — $19/mo recurring
- Payment Link: https://buy.stripe.com/test_cNi8wRbnZghE2CggPZ2cg00 — 7-day trial, then $19/mo
- All in **test mode**. Going live requires: Stripe identity verification + bank link, swap `sk_test_` → `sk_live_` in MCP config, recreate product/price/link in live mode (test-mode IDs do not carry over).

Manual flow:
1. Customer fills `CLIENT_INTAKE.md` (which contains the Payment Link URL) → completes Stripe checkout.
2. Operator gets Stripe email confirming the subscription.
3. Operator runs `provision_client.sh <slug> <email>`, edits config, fills in `billing.stripe_subscription_id`, flips `billing.status: pending → active`.
4. `assign_slot.py` validates the render slot. Local dispatcher picks them up next cycle.

This is fine for the first 10–20 customers. Cancel handling: Stripe sends a webhook on cancellation; check inbox weekly, edit `clients/<slug>/config.yaml` `billing.status: cancelled`. The send.py will skip them automatically.

**V2 — automated provisioning via Stripe MCP / webhook**:
- Stripe webhook posts to a small Flask endpoint on the Kali box.
- On `customer.subscription.created`: pull intake form data from the customer's metadata, run `provision_client.sh`, register the cloud routine via `RemoteTrigger.create`.
- On `customer.subscription.deleted`: flip `billing.status: cancelled`.
- The Stripe MCP would let Claude do this conversationally; for production a regular webhook handler is simpler and cheaper.

**V3 — hosted billing portal**: Stripe Customer Portal so customers can self-serve cancel/upgrade/payment-method-update.

## Real gotchas (the things that will bite us)

### 1. Pentest section dies for remote clients
Section 3 of Jacob's newsletter — the home network pentest — depends on the Kali box being on the same LAN as the target router. Joe Snuffy at his house in another state can't get this from our Kali. Three options:
- Drop the section for remote clients (default).
- **Premium tier**: ship a Raspberry Pi pre-configured to run the weekly hexstrike scan and push to a private GitHub repo we read from. ~$60 hardware cost, $20–30/mo premium.
- Substitute a "regional cyber threat brief" tied to the customer's metro instead.

### 2. Gmail sending caps
Free Gmail: 500 sends/day. Workspace: 2000/day. We're sending 1 message per customer per week so the cap is fine to ~50 weekly customers. Past that, switch to Postmark or AWS SES (~$0.01/email, much better deliverability, and your personal Gmail won't get flagged for "bulk" patterns). Budget for the migration around customer #30.

### 3. Render-cost variance
Cloud routine cost depends on how much WebSearch/WebFetch the agent does. Heavy news weeks (lots of CVEs, lots of events) push cost up. Hard cap at ~$5/render is achievable by tightening the prompt; we'd add a per-section content-budget enforcer.

### 4. Single point of failure
Kali at home goes offline (power, ISP, you reboot it) → no Tuesday email. Acceptable for first 10 customers. After that:
- Move `send.py` cron to a small VPS ($5/mo DigitalOcean droplet).
- Or move sending into the cloud routine itself using a transactional email API (cuts the local cron entirely; Anthropic routine handles render + send in one shot).

### 5. Privacy/legal
Storing customer prefs (location, vehicle they want, concerts they care about, paper trading account) on a personal Kali box is fine for friends-and-family. Past 10 customers consider:
- Encrypt `clients/` at rest.
- Terms of service + privacy policy (cookie-cutter template + lawyer review, ~$500 one-time).
- LLC formation (~$50 in TN state filing fees).

### 6. Section content scaling
Most sections (CrossFit news, EW brief, devotional, recipe, chess) are fully generic and reusable. Sections 7, 12, 14–17 are personalized via config. Adding a NEW section type for one customer who wants something we don't support yet costs renderer engineering time. Charge a one-time customization fee ($200) for non-standard sections.

## Roadmap

**Now (V1, single client live):**
- ✅ Render config-driven
- ✅ Multi-tenant directory layout
- ✅ Provisioning script
- ✅ Multi-client send.py
- ✅ Client intake form

**V2 (first 5 customers):**
- Stripe Payment Link in production
- Document the operator runbook (how to onboard, debug, cancel)
- Tighten render-cost ceiling per section
- Build a simple landing page (static HTML, GitHub Pages)

**V3 (10+ customers):**
- Stripe webhook automation
- Move send.py to VPS
- Migrate to SES for outbound
- Premium "home pentest" tier with shipped Pi
- Customer self-serve portal

**V4 (50+ customers):**
- LLC + insurance
- Switch outbound to dedicated newsletter-domain (better deliverability)
- A/B test sections — drop the ones nobody reads (instrument with tracking pixels or a per-section "useful?" 1-click survey)
- Multi-language support (single biggest expansion lever after we crack the English market)

## Risks worth naming

- **Anthropic pricing changes**: a 2× increase in API cost would cut margin in half. Mitigation: negotiate Enterprise pricing past 50 customers; build a fallback renderer using cheaper models for cost-sensitive sections.
- **Source rot**: if Wikimedia, Alpaca, or Ticketmaster change their interfaces, sections break silently. Mitigation: monitor for empty sections in pdf output; alert on >2 sections empty in a single render.
- **Customer churn**: weekly newsletters are easy to ignore. Mitigation: track open rate (server-side via tracking pixel or Mailgun-style analytics); reach out to silent customers at week 6 with a "is this still useful?" check-in.
- **Fraud / chargebacks**: low risk at this volume. Stripe Radar handles it.

## What success looks like

- **Month 3**: 10 paying customers at $19/mo = $190 MRR. Covers API costs and Stripe fees, breakeven on the operator's time.
- **Month 6**: 25 paying customers, mix of $19 and $29. ~$650 MRR. Self-funding; reinvest in landing page + automation.
- **Month 12**: 50 paying customers, average $29/mo, ~$1,450 MRR. Time to decide: keep as a side business, or invest in scale (full-time, agency, or sell).
