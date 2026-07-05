"""
tracker.py — read/write the application_tracker.csv.

Keyed by (Job Title, Company). Upserts rows so re-running the workflow updates
existing entries instead of duplicating them.
"""
from __future__ import annotations

import csv
from common import TRACKER_CSV, TRACKER_COLUMNS, today, add_days, ensure_dirs


def _key(title: str, company: str) -> str:
    return f"{(title or '').strip().lower()}|{(company or '').strip().lower()}"


def read_rows() -> list[dict]:
    if not TRACKER_CSV.exists():
        return []
    with open(TRACKER_CSV, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_rows(rows: list[dict]) -> None:
    ensure_dirs()
    with open(TRACKER_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=TRACKER_COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in TRACKER_COLUMNS})


def row_from_job(job: dict) -> dict:
    scam = job.get("scam_risk", "")
    barrier = job.get("credential_barrier", "None")
    rec = job.get("recommendation", "")
    if scam in ("High", "Reject") or barrier == "Hard":
        status = "Rejected by Filter"
        next_action = "Auto-rejected — do not apply"
    elif rec in ("Apply immediately", "Strong match"):
        status = "Reviewed"
        next_action = "Tailor resume & apply"
    elif rec == "Possible match":
        status = "Saved"
        next_action = "Apply only if strategic"
    else:
        status = "Reviewed"
        next_action = "Skip / weak match"

    return {
        "Date Found": job.get("date_found", today()),
        "Date Applied": "",
        "Job Title": job.get("job_title", ""),
        "Company": job.get("company", ""),
        "Location": job.get("location", ""),
        "Remote/Hybrid/On-site": job.get("work_mode", ""),
        "Salary": job.get("salary_range", ""),
        "Source": job.get("job_source", ""),
        "Application URL": job.get("application_url", ""),
        "Contact Name": "",
        "Contact Email": "",
        "Status": status,
        "Fit Score": job.get("fit_score", ""),
        "Scam Risk": scam,
        "Resume Version Used": job.get("best_resume_version", ""),
        "Cover Letter Used": "",
        "Follow-Up Date": "",
        "Interview Date": "",
        "Outcome": "",
        "Notes": (job.get("recommendation", "") + " | " + (job.get("reasoning", "")[:180])),
        "Next Action": next_action,
    }


def upsert_jobs(jobs: list[dict]) -> int:
    rows = read_rows()
    index = {_key(r["Job Title"], r["Company"]): i for i, r in enumerate(rows)}
    added = 0
    for job in jobs:
        new_row = row_from_job(job)
        k = _key(new_row["Job Title"], new_row["Company"])
        if k in index:
            existing = rows[index[k]]
            # preserve human-entered fields; refresh scores/recommendation
            for keep in ("Date Applied", "Contact Name", "Contact Email",
                         "Cover Letter Used", "Follow-Up Date", "Interview Date",
                         "Outcome"):
                new_row[keep] = existing.get(keep, "")
            # don't downgrade a manually advanced status
            if existing.get("Status") not in ("Found", "Reviewed", "Saved", "Rejected by Filter", ""):
                new_row["Status"] = existing["Status"]
            rows[index[k]] = new_row
        else:
            rows.append(new_row)
            index[k] = len(rows) - 1
            added += 1
    write_rows(rows)
    return added


def mark_applied(title: str, company: str, resume: str = "", cover: str = "") -> bool:
    rows = read_rows()
    k = _key(title, company)
    for r in rows:
        if _key(r["Job Title"], r["Company"]) == k:
            r["Status"] = "Applied"
            r["Date Applied"] = today()
            r["Follow-Up Date"] = add_days(today(), 3)
            if resume:
                r["Resume Version Used"] = resume
            if cover:
                r["Cover Letter Used"] = cover
            r["Next Action"] = "Follow up in 3 days"
            write_rows(rows)
            return True
    return False
