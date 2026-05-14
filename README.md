# Jacob's Gazette

Multi-tenant weekly newsletter service — generates a Word document per client, emails it on a per-client schedule.

This repo holds the **renderer, agent prompt, pipeline scripts, and per-client configs + assets**. Pentest reports and rendered `.docx` output live in the private repo (`jacobs-gazette-private`).

## Repo structure

```
jacobs-gazette-assets/
├── agent_prompt.md          # Parameterized generation prompt (CLIENT_SLUG, credentials injected at runtime)
├── render.py                # .docx renderer — takes content JSON + client config, produces newsletter
├── render_dispatcher.py     # Cron entry point (*/15 min): fires per-client renders when their window arrives
├── render_local.sh          # Wraps `claude -p` headless; symlinks /tmp/jg, exports credentials
├── send.py                  # Multi-tenant SMTP sender with per-client idempotency via .sent_log
├── assign_slot.py           # Provisioning validator: enforces 5-hr spacing on same-weekday render slots
├── provision_client.sh      # Onboarding script: scaffolds client dir, calls assign_slot.py
├── crossword_gen.py         # Crossword grid generator (PNG + clue JSON)
├── build_pentest_report.py  # Converts nmap XML → pentest section JSON
├── local_pentest.sh         # Sunday-night cron: runs hexstrike, pushes report to private repo
├── sample_content.json      # Example content JSON for testing render.py locally
├── sample_crossword_words.json
├── BUSINESS_PLAN.md         # Pricing, capacity model, migration plan
├── CLIENT_INTAKE.md         # Customer-facing intake form
└── clients/
    └── <slug>/
        ├── config.yaml      # Per-client spec: recipient, schedule, branding, enabled sections
        └── assets/
            ├── title_page.png        # Permanent Canva cover (reused every week)
            ├── header_logo.png
            └── ...                   # Section images regenerated weekly by the agent
```

## How a render works

1. `render_dispatcher.py` runs every 15 minutes via cron. For each client whose render window has arrived, it calls `render_local.sh <slug>`.
2. `render_local.sh` symlinks `/tmp/jg → ~/jacobs-gazette`, exports credentials, then runs `claude -p agent_prompt.md` in headless mode with `CLIENT_SLUG` injected.
3. The agent gathers content (WebSearch, WebFetch, Strava MCP, Alpaca REST, etc.), writes `output/<slug>_content.json`, and runs `render.py` to produce the `.docx`.
4. The `.docx` is committed and pushed to the private repo.
5. `send.py` (also cron'd every 15 min) detects the new file in the private repo and SMTPs it to the client.

## Render manually

```bash
# Full render with client branding
python3 render.py output/jacob_content.json output/newsletter_test.docx --config clients/jacob/config.yaml

# Check page count
soffice --headless --convert-to pdf output/newsletter_test.docx --outdir output/
pdfinfo output/newsletter_test.pdf | grep Pages
```

## Add a new client

```bash
bash provision_client.sh <slug> <recipient@email.com>
# Then edit clients/<slug>/config.yaml to set branding, sections, and schedule.
```
