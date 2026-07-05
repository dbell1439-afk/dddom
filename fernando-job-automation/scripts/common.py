"""
common.py — shared paths, data loading, and helpers for the job automation system.

Pure standard library. No network calls. Local-first.
"""
from __future__ import annotations

import json
import os
import re
import datetime as _dt
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent
DATA_DIR = ROOT / "data"
JOB_POSTS_DIR = ROOT / "job_posts"
OUTPUTS_DIR = ROOT / "outputs"
RESUMES_DIR = ROOT / "resumes"
COVER_LETTERS_DIR = ROOT / "cover_letters"
PROMPTS_DIR = ROOT / "prompts"

TRACKER_CSV = DATA_DIR / "application_tracker.csv"
JOBS_STORE = OUTPUTS_DIR / "jobs.json"  # normalized, scored jobs live here

TRACKER_COLUMNS = [
    "Date Found", "Date Applied", "Job Title", "Company", "Location",
    "Remote/Hybrid/On-site", "Salary", "Source", "Application URL",
    "Contact Name", "Contact Email", "Status", "Fit Score", "Scam Risk",
    "Resume Version Used", "Cover Letter Used", "Follow-Up Date",
    "Interview Date", "Outcome", "Notes", "Next Action",
]

STATUSES = [
    "Found", "Reviewed", "Rejected by Filter", "Saved", "Resume Tailored",
    "Applied", "Follow-Up Sent", "Recruiter Contacted", "Interview Requested",
    "Interview Completed", "Offer", "Rejected", "Closed",
]


# ---------------------------------------------------------------------------
# Data loaders (cached)
# ---------------------------------------------------------------------------
_cache: dict[str, object] = {}


def _load_json(name: str) -> dict:
    if name in _cache:
        return _cache[name]  # type: ignore[return-value]
    with open(DATA_DIR / name, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    _cache[name] = data
    return data


def load_profile() -> dict:
    return _load_json("candidate_profile.json")


def load_scam_filters() -> dict:
    return _load_json("scam_filters.json")


def load_target_companies() -> dict:
    return _load_json("target_companies.json")


def load_job_sources() -> dict:
    return _load_json("job_sources.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def today() -> str:
    return _dt.date.today().isoformat()


def add_days(date_str: str, days: int) -> str:
    d = _dt.date.fromisoformat(date_str)
    return (d + _dt.timedelta(days=days)).isoformat()


def slugify(text: str, maxlen: int = 60) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    return text.strip("-")[:maxlen]


def find_patterns(text: str, patterns: list[str]) -> list[str]:
    """Return the list of regex patterns that match (case-insensitive)."""
    hits = []
    for p in patterns:
        try:
            if re.search(p, text, re.IGNORECASE):
                hits.append(p)
        except re.error:
            if p.lower() in text.lower():
                hits.append(p)
    return hits


def parse_salary(text: str) -> tuple[int | None, int | None]:
    """Best-effort salary band extraction. Handles $/hr and $/yr and K notation."""
    t = text.replace(",", "")
    is_hourly = bool(re.search(r"per hour|/\s*hr|hourly|/hour", t, re.IGNORECASE))
    nums: list[int] = []
    for m in re.finditer(r"\$?\s*(\d{2,3}(?:\.\d+)?)\s*[kK]\b", t):
        nums.append(int(float(m.group(1)) * 1000))
    if not nums:
        for m in re.finditer(r"\$\s*(\d{4,7})(?:\.\d+)?", t):
            nums.append(int(float(m.group(1))))
    if not nums and is_hourly:
        for m in re.finditer(r"\$?\s*(\d{1,3}(?:\.\d{1,2})?)\s*(?:per hour|/\s*hr|hourly|/hour)", t, re.IGNORECASE):
            nums.append(int(float(m.group(1)) * 2080))
    if not nums:
        return None, None
    nums = sorted(set(nums))
    if is_hourly and max(nums) < 200:  # convert stray hourly numbers to annual
        nums = [n * 2080 for n in nums]
    lo = min(nums)
    hi = max(nums)
    # sanity: ignore absurd values
    if lo < 10000:
        lo = None
    if hi < 10000:
        hi = None
    return lo, hi


def detect_work_mode(text: str) -> str:
    t = text.lower()
    if re.search(r"\bremote\b|work from home|\bwfh\b|telecommute", t):
        if "hybrid" in t:
            return "Hybrid"
        return "Remote"
    if "hybrid" in t:
        return "Hybrid"
    if re.search(r"on-?site|in-person|in office", t):
        return "On-site"
    return "Unknown"


def ensure_dirs() -> None:
    for d in (DATA_DIR, JOB_POSTS_DIR, OUTPUTS_DIR, RESUMES_DIR, COVER_LETTERS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_jobs_store() -> list[dict]:
    if JOBS_STORE.exists():
        with open(JOBS_STORE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return []


def save_jobs_store(jobs: list[dict]) -> None:
    ensure_dirs()
    with open(JOBS_STORE, "w", encoding="utf-8") as fh:
        json.dump(jobs, fh, indent=2, ensure_ascii=False)
