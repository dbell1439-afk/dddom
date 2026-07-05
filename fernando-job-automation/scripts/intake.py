"""
intake.py — normalize raw job postings into the canonical schema.

Accepts:
  - .txt files in /job_posts (raw pasted description; first line may be a URL)
  - a CSV export from a job board (--csv)

Produces normalized job dicts (not yet scored). Scoring/filtering happens in
the workflow. Pure stdlib.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

from common import (
    JOB_POSTS_DIR, today, slugify, parse_salary, detect_work_mode,
    load_job_sources,
)

_URL_RE = re.compile(r"https?://[^\s)]+")


def _extract_url(text: str) -> str:
    m = _URL_RE.search(text)
    return m.group(0) if m else ""


def _guess_field(text: str, labels: list[str]) -> str:
    """Find a line that starts with one of the labels and return the value."""
    for line in text.splitlines():
        low = line.lower().strip()
        for lab in labels:
            if low.startswith(lab.lower()):
                return line.split(":", 1)[1].strip() if ":" in line else line[len(lab):].strip()
    return ""


def _extract_bullets(text: str, section_keywords: list[str]) -> list[str]:
    """Pull bullet-ish lines under a section header matching keywords."""
    lines = text.splitlines()
    out: list[str] = []
    capture = False
    for line in lines:
        low = line.lower().strip()
        if any(k in low for k in section_keywords) and len(low) < 80:
            capture = True
            continue
        if capture:
            if not line.strip():
                if out:
                    break
                continue
            if re.match(r"^\s*[-*•\d.]", line) or (len(line.strip()) > 0 and line[0].isspace()):
                out.append(re.sub(r"^\s*[-*•\d.\)]+\s*", "", line).strip())
            elif low.endswith(":") and len(low) < 60:
                break
            else:
                out.append(line.strip())
            if len(out) >= 15:
                break
    return [o for o in out if o]


def _extract_keywords(text: str) -> list[str]:
    from common import load_profile
    profile = load_profile()
    bank = profile["ats_keyword_bank"]
    all_kw: list[str] = []
    for group in bank.values():
        all_kw.extend(group)
    tl = text.lower()
    return sorted({kw for kw in all_kw if kw.lower() in tl})


def normalize_text(raw: str, source_name: str = "manual") -> dict:
    url = _extract_url(raw)
    title = _guess_field(raw, ["job title", "title", "position", "role"])
    if not title:
        # first non-URL, non-empty line as a fallback title
        for line in raw.splitlines():
            s = line.strip()
            if s and not _URL_RE.match(s):
                title = s[:100]
                break
    company = _guess_field(raw, ["company", "employer", "organization"])
    location = _guess_field(raw, ["location", "based in", "city"])
    salary_field = _guess_field(raw, ["salary", "pay", "compensation", "rate"])
    deadline = _guess_field(raw, ["apply by", "deadline", "closing date", "applications close"])

    lo, hi = parse_salary(salary_field or raw)
    mode = detect_work_mode(raw)

    responsibilities = _extract_bullets(raw, ["responsibilities", "duties", "what you", "you will", "essential functions"])
    required = _extract_bullets(raw, ["requirements", "required", "qualifications", "must have", "minimum qualifications"])
    preferred = _extract_bullets(raw, ["preferred", "nice to have", "desired", "a plus"])

    job = {
        "job_id": slugify(f"{company or 'unknown'}-{title or 'role'}-{today()}"),
        "job_title": title or "(untitled)",
        "company": company or "(unknown)",
        "location": location or ("Remote" if mode == "Remote" else "(unknown)"),
        "work_mode": mode,
        "salary_range": salary_field or (f"${lo:,}-${hi:,}" if lo and hi else ""),
        "salary_min_usd": lo,
        "salary_max_usd": hi,
        "job_source": source_name,
        "application_url": url,
        "date_found": today(),
        "deadline": deadline or None,
        "required_credentials": required[:12],
        "preferred_credentials": preferred[:12],
        "required_experience": " ".join(required[:12]),
        "keywords": _extract_keywords(raw),
        "responsibilities": responsibilities[:15],
        "raw_text": raw,
    }
    return job


def normalize_txt_files() -> list[dict]:
    jobs = []
    for path in sorted(JOB_POSTS_DIR.glob("*.txt")):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if not raw.strip():
            continue
        jobs.append(normalize_text(raw, source_name=path.stem))
    return jobs


def normalize_csv(csv_path: str) -> list[dict]:
    jobs = []
    with open(csv_path, newline="", encoding="utf-8", errors="ignore") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            # be flexible about column names
            lower = {k.lower().strip(): (v or "").strip() for k, v in row.items() if k}
            title = lower.get("title") or lower.get("job title") or lower.get("position") or ""
            company = lower.get("company") or lower.get("employer") or ""
            location = lower.get("location") or lower.get("city") or ""
            url = lower.get("url") or lower.get("application url") or lower.get("link") or ""
            salary = lower.get("salary") or lower.get("pay") or lower.get("compensation") or ""
            desc = lower.get("description") or lower.get("summary") or ""
            raw = "\n".join([
                f"Job Title: {title}", f"Company: {company}", f"Location: {location}",
                f"Salary: {salary}", url, desc,
            ])
            job = normalize_text(raw, source_name=Path(csv_path).stem)
            if url:
                job["application_url"] = url
            jobs.append(job)
    return jobs


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--csv":
        js = normalize_csv(sys.argv[2])
    else:
        js = normalize_txt_files()
    print(f"Normalized {len(js)} job(s).")
    for j in js:
        print(f"  - {j['job_title']} @ {j['company']} [{j['work_mode']}]")
