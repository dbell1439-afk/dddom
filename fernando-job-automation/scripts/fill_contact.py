"""
fill_contact.py — stamp real contact details into every resume + the cover-letter
template, replacing the [phone] / [email] / [LinkedIn] placeholders.

Fill data/contact_info.json first, then run:  python3 scripts/jobbot.py contact
Idempotent: safe to run repeatedly. Only replaces placeholder tokens and previously
stamped values, so re-running after editing contact_info.json updates cleanly.
"""
from __future__ import annotations

import json
from pathlib import Path

from common import DATA_DIR, RESUMES_DIR, COVER_LETTERS_DIR

CONTACT_PATH = DATA_DIR / "contact_info.json"

# token in files  ->  key in contact_info.json
TOKENS = {
    "[phone]": "phone",
    "[email]": "email",
    "[LinkedIn]": "linkedin",
}


def _load_contact() -> dict:
    with open(CONTACT_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def fill() -> int:
    contact = _load_contact()
    # Skip values still left as placeholders so we don't stamp junk.
    replacements = {
        token: contact.get(key, token)
        for token, key in TOKENS.items()
        if contact.get(key) and contact.get(key) != token
    }
    if not replacements:
        print("No real contact values set yet. Edit data/contact_info.json "
              "(phone/email/linkedin), then run this again.")
        return 0

    targets = list(RESUMES_DIR.glob("*.md")) + [COVER_LETTERS_DIR / "_TEMPLATE.md"]
    changed = 0
    for path in targets:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        new = text
        for token, value in replacements.items():
            new = new.replace(token, value)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed += 1
    print(f"Stamped contact info into {changed} file(s): "
          f"{', '.join(f'{k}->{v}' for k, v in replacements.items())}")
    return changed


if __name__ == "__main__":
    fill()
