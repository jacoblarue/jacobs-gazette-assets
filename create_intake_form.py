#!/usr/bin/env python3
"""
Create the Jacob's Gazette client intake Google Form via the Forms API.
Run once. Prints the edit URL and public fill-in URL when done.

Prerequisites:
  1. In Google Cloud Console, enable the Google Forms API and Google Drive API
     for your project.
  2. Create an OAuth 2.0 Client ID (Desktop app), download the JSON, and save it
     to ~/.config/google-oauth-client.json
  3. Run this script — it will open a browser for one-time consent, then save
     ~/.config/google-oauth-token.json for future runs.
"""

import json
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/drive",
]
CLIENT_SECRETS = os.path.expanduser("~/.config/google-oauth-client.json")
TOKEN_PATH = os.path.expanduser("~/.config/google-oauth-token.json")


def get_creds():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return creds


def ti(text):
    """TextItem — section header / informational paragraph."""
    return {"textItem": {}, "title": text}


def pb():
    """PageBreakItem — new section in the form."""
    return {"pageBreakItem": {}}


def short(title, required=False, description=None):
    item = {
        "title": title,
        "questionItem": {
            "question": {
                "required": required,
                "textQuestion": {"paragraph": False},
            }
        },
    }
    if description:
        item["description"] = description
    return item


def para(title, required=False, description=None):
    item = {
        "title": title,
        "questionItem": {
            "question": {
                "required": required,
                "textQuestion": {"paragraph": True},
            }
        },
    }
    if description:
        item["description"] = description
    return item


def radio(title, options, required=False, description=None):
    item = {
        "title": title,
        "questionItem": {
            "question": {
                "required": required,
                "choiceQuestion": {
                    "type": "RADIO",
                    "options": [{"value": o} for o in options],
                },
            }
        },
    }
    if description:
        item["description"] = description
    return item


def checkbox(title, options, required=False, description=None):
    item = {
        "title": title,
        "questionItem": {
            "question": {
                "required": required,
                "choiceQuestion": {
                    "type": "CHECKBOX",
                    "options": [{"value": o} for o in options],
                },
            }
        },
    }
    if description:
        item["description"] = description
    return item


def dropdown(title, options, required=False, description=None):
    item = {
        "title": title,
        "questionItem": {
            "question": {
                "required": required,
                "choiceQuestion": {
                    "type": "DROP_DOWN",
                    "options": [{"value": o} for o in options],
                },
            }
        },
    }
    if description:
        item["description"] = description
    return item


ITEMS = [
    # ── Section 1: Basics ──────────────────────────────────────────────────────
    ti("Fill this out and send it back. Anything you skip, we use a sensible default. Most clients finish in 15 minutes."),
    short("Your name", required=True),
    short("Email address where the newsletter should arrive", required=True),
    short(
        "What should the newsletter be called?",
        required=True,
        description='e.g. "Joe\'s Dispatch", "The Snuffy Brief", "The Monday Mash"',
    ),
    short(
        "One-line tagline",
        description='3–5 words separated by bullets, e.g. "Faith • Tech • Tennessee • Iron"',
    ),
    short(
        "Short header phrase",
        description='e.g. "A Weekly Brief", "Tuesday Edition", "The Monday Mash"',
    ),

    # ── Section 2: Schedule ────────────────────────────────────────────────────
    pb(),
    radio(
        "Day of the week",
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        required=True,
    ),
    short("Time of day", required=True, description="24-hour format, e.g. 07:00 or 19:30"),
    dropdown(
        "Time zone",
        [
            "America/New_York",
            "America/Chicago",
            "America/Denver",
            "America/Los_Angeles",
            "America/Phoenix",
            "America/Anchorage",
            "Pacific/Honolulu",
        ],
        required=True,
    ),

    # ── Section 3: Branding ────────────────────────────────────────────────────
    pb(),
    short(
        "Primary color — headers and borders",
        description='Hex code (#0A1F3D) or a vibe ("navy blue, like a Penn State pennant" / "deep forest green")',
    ),
    short(
        "Accent color — highlights and section rules",
        description="Hex code or vibe description",
    ),
    para(
        "Logo",
        description=(
            "Describe your logo or paste a link to it. Ideal spec: PNG, transparent background, ~900×225px, "
            "looks good on a dark background. If you don't have one, leave this blank and we'll generate one "
            "in your colors via Canva. Email the actual file to jacoblarue7@gmail.com."
        ),
    ),

    # ── Section 4: Location ────────────────────────────────────────────────────
    pb(),
    short("City, State", description='e.g. "Clarksville, TN"'),
    short(
        "Regional descriptor",
        description='e.g. "Tennessee/Kentucky", "Triangle NC", "Bay Area"',
    ),

    # ── Section 5: Sections ────────────────────────────────────────────────────
    pb(),
    checkbox(
        "Which sections do you want? (check all that apply)",
        [
            "EW Industry Brief — electromagnetic warfare news (good if you work defense/aerospace)",
            "Cyber & Pentesting Roundup — CVEs, breaches, red-team news",
            "Home Network Security Report — automated weekly pentest of your router (requires a Pi we ship)",
            "CrossFit News — Open/Semifinals/Games progression, athlete news",
            "College Football Watch — anchor team or general coverage",
            "Something Good in the World — one uplifting story a week",
            "Local Events — upcoming events in your city/region",
            "Verse to Memorize — weekly devotional with reflection",
            "Last Week on Strava — your weekly running/cycling stats",
            "Opening of the Week — chess opening rotation",
            "Crossword — themed weekly puzzle",
            "Life Hacks — one actionable hack per week",
            "Recipe of the Week — filtered by your dietary preferences",
            "Upcoming CrossFit Comps — competitions in your region",
            "Cheap Flights — deal alerts from your home airport",
            "Vehicle Watch — listings matching your target spec",
            "Concert Watch — artist tour alerts + Airbnb finder",
            "Alpaca Paper Trading Snapshot — weekly portfolio summary",
        ],
        required=True,
        description="The newsletter targets 10–20 pages — fewer sections = shorter newsletter.",
    ),
    short(
        "College Football: anchor team?",
        description='e.g. "Tennessee Volunteers", "UNC Tar Heels". Leave blank for general coverage.',
    ),
    radio(
        "Verse to Memorize: Bible translation",
        ["ESV", "NIV", "KJV", "NASB", "NLT"],
    ),
    short(
        "Last Week on Strava: your Strava athlete ID or profile URL",
        description="Leave blank to skip.",
    ),
    radio(
        "Life Hacks: category",
        ["Financial", "Productivity", "Health", "Parenting", "Mixed"],
    ),
    para(
        "Recipe: dietary constraints",
        description='e.g. "high-protein, max 600 cal/serving, max 45 min, 4 servings"',
    ),
    short(
        "CrossFit Comps: states/regions to monitor",
        description='e.g. "TN, NC, GA"',
    ),
    short(
        "Cheap Flights: origin airport + destinations",
        description='e.g. "BNA → PHX, LAX, DEN"',
    ),
    para(
        "Cheap Flights: when do you want to travel?",
        description=(
            'Describe your travel anchor in plain English — we\'ll figure out the dates. '
            'e.g. "weekends I\'m off work", "school holidays for my kids", '
            '"Fort Campbell training holidays", "every other weekend in fall"'
        ),
    ),
    para(
        "Vehicle Watch: target spec",
        description='e.g. "2020–2023 Toyota Tacoma TRD Off-Road, 4x4, white or grey, under $38k, under 60k miles"',
    ),
    para(
        "Concert Watch: artist + travel preferences",
        description=(
            'e.g. "Morgan Wallen, home metro Nashville, within 300 miles, '
            '2-bedroom Airbnb 4.7+ stars within 5 miles of venue"'
        ),
    ),
    para(
        "Alpaca Paper Trading: API keys",
        description=(
            "If you want this section:\n"
            "1. Sign up free at https://app.alpaca.markets/signup (no funding needed)\n"
            "2. Go to Paper Dashboard → API Keys → Generate\n"
            "3. Paste both your Key ID (starts with PK) and Secret Key here.\n"
            "Your account stays in your name; we only read your portfolio for the weekly summary."
        ),
    ),

    # ── Section 6: Anything else ───────────────────────────────────────────────
    pb(),
    para(
        "Specific topics you want covered weekly that aren't in the list above",
        description="Niche beats, hobbies, local teams, anything.",
    ),
    para("Topics or framings to avoid"),
    radio(
        "Tone preference",
        ["Terse and direct", "Conversational", "Wry / dry humor", "Formal"],
    ),

    # ── Section 7: Payment ─────────────────────────────────────────────────────
    pb(),
    ti(
        "Subscribe at https://buy.stripe.com/test_cNi8wRbnZghE2CggPZ2cg00\n\n"
        "$19/month after a 7-day free trial — your card isn't charged until day 8. "
        "Cancel anytime. We start your spec review the moment you complete checkout."
    ),
]


def main():
    creds = get_creds()
    forms = build("forms", "v1", credentials=creds)

    # Create the shell form
    form = forms.forms().create(body={"info": {"title": "Jacob's Gazette — Client Intake"}}).execute()
    form_id = form["formId"]

    # Build batchUpdate requests
    requests = []
    for idx, item in enumerate(ITEMS):
        requests.append({
            "createItem": {
                "item": item,
                "location": {"index": idx},
            }
        })

    forms.forms().batchUpdate(
        formId=form_id,
        body={"requests": requests},
    ).execute()

    # Fetch final form for URLs
    result = forms.forms().get(formId=form_id).execute()
    responder_uri = result.get("responderUri", f"https://docs.google.com/forms/d/{form_id}/viewform")
    edit_uri = f"https://docs.google.com/forms/d/{form_id}/edit"

    print(f"\nForm created successfully!")
    print(f"  Edit URL:  {edit_uri}")
    print(f"  Share URL: {responder_uri}")
    print(f"\nSave the Share URL — that's what you embed in CLIENT_INTAKE.md and the Stripe confirmation email.")


if __name__ == "__main__":
    main()
