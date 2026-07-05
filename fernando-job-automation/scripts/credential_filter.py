"""
credential_filter.py — detects hard, non-negotiable credential/license barriers
that Fernando does not hold, unless the posting offers an acceptable pathway.

Returns a credential_barrier of: None | Soft | Hard
- Hard  : posting hard-requires a credential he lacks with NO pathway  -> heavy penalty / usually do-not-apply
- Soft  : credential mentioned as preferred, or a pathway is offered    -> minor penalty
- None  : no blocking credential requirement
"""
from __future__ import annotations

import re
from common import load_profile

# Phrases that signal a hard requirement
_HARD_REQ = [
    r"required", r"must (?:have|hold|possess)", r"minimum qualifications?",
    r"is required", r"required qualifications?",
]
# Phrases that signal a pathway / softening
_PATHWAY = [
    r"or equivalent", r"equivalent experience", r"in lieu of",
    r"foreign (?:degree|credential|equivalen)", r"pending certification",
    r"within \d+\s*(?:months|days)", r"trainee", r"apprentice",
    r"will train", r"eligible to (?:sit|obtain)", r"willing to obtain",
    r"preferred", r"nice to have", r"a plus", r"desired",
]

# Credential -> patterns Fernando does NOT hold (from profile.not_held)
_BLOCKING = {
    "ASCP MLS/MT": [r"ascp", r"\bmls\b", r"\bmt\s*\(?ascp\)?", r"medical (?:lab|laboratory) scientist", r"medical technologist"],
    "AAB MT": [r"\baab\b", r"american association of bioanalysts"],
    "FL lab license": [r"florida (?:clinical )?(?:lab|laboratory) (?:license|licensure|personnel)", r"\bclt\b license", r"\bcls\b license", r"technologist license"],
    "Cytotechnologist CT(ASCP)": [r"ct\s*\(?ascp\)?", r"cytotechnologist", r"cytotech certification"],
    "RN": [r"\brn\b", r"registered nurse", r"nursing license"],
    "MD/DO": [r"\bm\.?d\.?\b", r"\bd\.?o\.?\b", r"physician license"],
    "PA": [r"physician assistant", r"\bpa-?c\b"],
    "PharmD": [r"pharm\.?d", r"pharmacist license"],
}


def _window(text: str, match_start: int, size: int = 160) -> str:
    lo = max(0, match_start - size)
    hi = min(len(text), match_start + size)
    return text[lo:hi]


def assess_credentials(job: dict) -> dict:
    text = job.get("raw_text") or " ".join(
        [job.get("required_experience", "")] + (job.get("required_credentials") or [])
        + (job.get("responsibilities") or [])
    )
    tl = text.lower()

    barriers: list[str] = []
    hard = False
    soft = False

    for cred, patterns in _BLOCKING.items():
        for p in patterns:
            for m in re.finditer(p, tl):
                context = _window(tl, m.start())
                has_hard = any(re.search(h, context) for h in _HARD_REQ)
                has_pathway = any(re.search(pw, context) for pw in _PATHWAY)
                if has_hard and not has_pathway:
                    hard = True
                    barriers.append(f"HARD: '{cred}' appears required with no pathway")
                elif has_pathway:
                    soft = True
                    barriers.append(f"SOFT: '{cred}' mentioned but pathway/equivalency/preferred offered")
                else:
                    soft = True
                    barriers.append(f"SOFT: '{cred}' mentioned (not clearly hard-required)")
                break  # one hit per credential is enough

    if hard:
        barrier = "Hard"
    elif soft:
        barrier = "Soft"
    else:
        barrier = "None"

    # de-duplicate barriers preserving order
    seen = set()
    uniq = []
    for b in barriers:
        if b not in seen:
            seen.add(b)
            uniq.append(b)

    return {
        "credential_barrier": barrier,
        "credential_notes": uniq,
    }
