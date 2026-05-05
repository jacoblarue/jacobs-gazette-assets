# Jacob's Gazette

Weekly automated newsletter — generated as a Word document, emailed every Monday.

This repo holds the **renderer + assets**. Pentest reports and other private data live in a separate private repo.

## Files

- `render.py` — `.docx` renderer; takes a content JSON and produces the newsletter
- `crossword_gen.py` — crossword grid generator (PNG + clue list)
- `build_pentest_report.py` — converts nmap XML output into the pentest section's JSON shape
- `local_pentest.sh` — Sunday-night cron that runs nmap and pushes the pentest report to the private repo
- `assets/header_logo.png` — newsletter masthead

## Render manually

```bash
python3 render.py content.json output/newsletter.docx
```
