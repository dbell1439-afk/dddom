#!/usr/bin/env python3
"""
jobbot.py — the daily command-line workflow for Fernando's job automation system.

Everything is local-first and offline. No API keys, no network calls.

Commands
--------
  python3 jobbot.py intake              Import + normalize jobs from /job_posts (*.txt)
  python3 jobbot.py intake --csv FILE   Import jobs from a job-board CSV export
  python3 jobbot.py review              Score everything and print recommendations
  python3 jobbot.py daily               Full pipeline: intake -> filter -> score ->
                                        dedupe -> rank -> update tracker -> queue
  python3 jobbot.py queue               Show the current prioritized application queue
  python3 jobbot.py applied "Title" "Company"   Mark a job as applied (sets follow-up)
  python3 jobbot.py report              Generate the weekly strategy report
  python3 jobbot.py contact             Stamp data/contact_info.json into all resumes
  python3 jobbot.py xlsx                Rebuild data/application_tracker.xlsx
  python3 jobbot.py card "Title" "Company"      Print the single-job output card

Run `python3 jobbot.py daily` once a day. That is the core loop.
"""
from __future__ import annotations

import sys

from common import (
    today, add_days, load_jobs_store, save_jobs_store, OUTPUTS_DIR, ensure_dirs,
)
import intake
from scam_filter import score_scam
from credential_filter import assess_credentials
from scoring import score_job, best_resume
import tracker


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
import re as _re
from difflib import SequenceMatcher


def _norm_title(title: str) -> str:
    """Normalize a title for fuzzy comparison: lowercase, drop seniority level
    markers (I/II/III, 1/2/3, sr/jr), punctuation, and collapse whitespace."""
    t = (title or "").lower()
    t = _re.sub(r"\b(i{1,3}|iv|v|1|2|3|sr|jr|senior|junior|lead|level\s*\d)\b", " ", t)
    t = _re.sub(r"[^a-z0-9 ]+", " ", t)
    return _re.sub(r"\s+", " ", t).strip()


def _norm_url(url: str) -> str:
    """Strip tracking params/fragments so the same posting shared via different
    links collapses to one entry."""
    u = (url or "").strip().lower()
    u = _re.sub(r"[#?].*$", "", u)          # drop query + fragment
    return u.rstrip("/")


def _dedupe(jobs: list[dict]) -> list[dict]:
    """De-duplicate by canonical URL first, then by fuzzy title+company.

    This catches the same job reposted across boards (different URLs, near-
    identical titles) and altered-company-name repostings of the same role.
    Keeps the first occurrence (earlier = usually the direct-employer source).
    """
    kept: list[dict] = []
    seen_urls: set[str] = set()
    for j in jobs:
        url = _norm_url(j.get("application_url", ""))
        if url and url in seen_urls:
            continue
        nt = _norm_title(j.get("job_title", ""))
        comp = (j.get("company", "") or "").strip().lower()
        is_dupe = False
        for k in kept:
            same_company = SequenceMatcher(None, comp, (k.get("company", "") or "").lower()).ratio() > 0.9
            same_title = SequenceMatcher(None, nt, _norm_title(k.get("job_title", ""))).ratio() > 0.9
            if same_company and same_title:
                is_dupe = True
                break
        if is_dupe:
            continue
        if url:
            seen_urls.add(url)
        kept.append(j)
    return kept


def _evaluate(job: dict) -> dict:
    job.update(score_scam(job))
    job.update(assess_credentials(job))
    job["best_resume_version"] = best_resume(job)
    job.update(score_job(job))
    job["cover_letter_needed"] = job.get("recommendation") in ("Apply immediately", "Strong match")
    job["follow_up_date"] = None
    return job


def cmd_intake(args: list[str]) -> list[dict]:
    if len(args) >= 2 and args[0] == "--csv":
        jobs = intake.normalize_csv(args[1])
    else:
        jobs = intake.normalize_txt_files()
    print(f"Imported {len(jobs)} raw posting(s) from job_posts/.")
    return jobs


def cmd_daily(args: list[str]) -> None:
    ensure_dirs()
    # 1. intake
    if len(args) >= 2 and args[0] == "--csv":
        jobs = intake.normalize_csv(args[1])
    else:
        jobs = intake.normalize_txt_files()

    # merge with any previously stored jobs so the store is cumulative
    stored = load_jobs_store()
    combined = stored + jobs

    # 2. dedupe
    combined = _dedupe(combined)

    # 3-6. filter + score
    for job in combined:
        _evaluate(job)

    # sort by probability then fit
    combined.sort(key=lambda j: (j.get("probability_score", 0), j.get("fit_score", 0)), reverse=True)
    save_jobs_store(combined)

    # 9. update tracker
    added = tracker.upsert_jobs(combined)

    # 7. recommend top 5-10
    apply_now = [j for j in combined if j["decision"] == "Apply" and j["recommendation"] in ("Apply immediately", "Strong match")]
    strategic = [j for j in combined if j["decision"] == "Apply" and j["recommendation"] == "Possible match"]
    rejected = [j for j in combined if j["decision"] == "Do Not Apply"]

    print("\n" + "=" * 70)
    print(f"DAILY RUN — {today()}")
    print("=" * 70)
    print(f"Jobs evaluated: {len(combined)}   New to tracker: {added}")
    print(f"Auto-rejected (scam/credential/weak): {len(rejected)}")
    print(f"Apply-now queue: {len(apply_now)}   Strategic maybes: {len(strategic)}")

    print("\n--- TOP APPLICATION QUEUE (apply these first) ---")
    for i, j in enumerate(apply_now[:10], 1):
        _print_line(i, j)

    if strategic:
        print("\n--- STRATEGIC MAYBES (apply only if time allows) ---")
        for i, j in enumerate(strategic[:5], 1):
            _print_line(i, j)

    _write_queue_file(apply_now, strategic, rejected)
    print(f"\nQueue written to outputs/application_queue.md")
    print("Next: open outputs/application_queue.md, then use the prompts in /prompts")
    print("to generate tailored resumes & cover letters for the apply-now jobs.")


def _print_line(i: int, j: dict) -> None:
    print(f"  {i:>2}. [{j['fit_score']:>4}/{j['probability_score']:>4}] "
          f"{j['job_title']} @ {j['company']} "
          f"({j['work_mode']}, {j.get('salary_range') or 'salary n/a'}) "
          f"-> {j['recommendation']} | resume: {j['best_resume_version']}")


def _write_queue_file(apply_now, strategic, rejected) -> None:
    ensure_dirs()
    lines = [f"# Application Queue — {today()}\n"]
    lines.append("## Apply now (highest probability first)\n")
    if not apply_now:
        lines.append("_No apply-now jobs today. Import more postings into `job_posts/`._\n")
    for i, j in enumerate(apply_now, 1):
        lines.append(_card_md(i, j))
    lines.append("\n## Strategic maybes\n")
    if not strategic:
        lines.append("_None._\n")
    for i, j in enumerate(strategic, 1):
        lines.append(_card_md(i, j))
    lines.append(f"\n## Auto-rejected: {len(rejected)} (see tracker for reasons)\n")
    for j in rejected[:25]:
        reason = "scam" if j.get("scam_risk") in ("High", "Reject") else (
            "hard credential barrier" if j.get("credential_barrier") == "Hard" else "weak fit")
        lines.append(f"- {j['job_title']} @ {j['company']} — {reason} (fit {j['fit_score']})")
    (OUTPUTS_DIR / "application_queue.md").write_text("\n".join(lines), encoding="utf-8")


def _card_md(i: int, j: dict) -> str:
    return "\n".join([
        f"### {i}. {j['job_title']} @ {j['company']}",
        f"- **Location / Mode:** {j['location']} — {j['work_mode']}",
        f"- **Salary:** {j.get('salary_range') or 'not listed'}",
        f"- **Source / URL:** {j['job_source']} — {j['application_url'] or 'n/a'}",
        f"- **Scam Risk:** {j['scam_risk']}   **Credential Barrier:** {j['credential_barrier']}",
        f"- **Fit Score:** {j['fit_score']}/100   **Probability:** {j['probability_score']}/100",
        f"- **Recommendation:** {j['recommendation']}   **Decision:** {j['decision']}",
        f"- **Best Resume:** {j['best_resume_version']}   **Cover Letter Needed:** {j['cover_letter_needed']}",
        f"- **Keywords matched:** {', '.join(j.get('keywords', [])[:12]) or '—'}",
        f"- **Why:** {j.get('reasoning', '')[:400]}",
        "",
    ])


def cmd_card(args: list[str]) -> None:
    if len(args) < 2:
        print('Usage: jobbot.py card "Job Title" "Company"')
        return
    title, company = args[0].lower(), args[1].lower()
    for j in load_jobs_store():
        if title in j.get("job_title", "").lower() and company in j.get("company", "").lower():
            print(_output_card(j))
            return
    print("No matching job found in the store. Run `daily` first.")


def _output_card(j: dict) -> str:
    return "\n".join([
        f"Job Title:        {j['job_title']}",
        f"Company:          {j['company']}",
        f"Location:         {j['location']} ({j['work_mode']})",
        f"Salary:           {j.get('salary_range') or 'not listed'}",
        f"Source:           {j['job_source']}",
        f"Application URL:  {j['application_url'] or 'n/a'}",
        f"Scam Risk:        {j['scam_risk']}",
        f"Credential Barrier: {j['credential_barrier']}",
        f"Fit Score:        {j['fit_score']}/100",
        f"Probability Score:{j['probability_score']}/100",
        f"Recommendation:   {j['recommendation']}",
        f"Best Resume Version: {j['best_resume_version']}",
        f"Cover Letter Needed: {j['cover_letter_needed']}",
        f"Follow-Up Date:   {j.get('follow_up_date') or '(set when applied)'}",
        f"Reasoning:        {j.get('reasoning','')}",
        f"Decision:         {j['decision']}",
    ])


def cmd_queue(_args: list[str]) -> None:
    jobs = load_jobs_store()
    queue = [j for j in jobs if j.get("decision") == "Apply"]
    queue.sort(key=lambda j: (j.get("probability_score", 0), j.get("fit_score", 0)), reverse=True)
    if not queue:
        print("Queue empty. Run `python3 jobbot.py daily` after adding postings to job_posts/.")
        return
    print(f"Application queue ({len(queue)} jobs), highest probability first:\n")
    for i, j in enumerate(queue, 1):
        _print_line(i, j)


def cmd_applied(args: list[str]) -> None:
    if len(args) < 2:
        print('Usage: jobbot.py applied "Job Title" "Company" [resume] [cover]')
        return
    resume = args[2] if len(args) > 2 else ""
    cover = args[3] if len(args) > 3 else ""
    if tracker.mark_applied(args[0], args[1], resume, cover):
        print(f"Marked applied: {args[0]} @ {args[1]}. Follow-up set for {add_days(today(),3)}.")
    else:
        print("No matching tracker row found. Check the exact Title/Company.")


def cmd_review(_args: list[str]) -> None:
    jobs = intake.normalize_txt_files()
    for j in jobs:
        _evaluate(j)
        print("\n" + _output_card(j))


def cmd_report(_args: list[str]) -> None:
    import weekly_report
    path = weekly_report.generate()
    print(f"Weekly report written to {path}")


def cmd_xlsx(_args: list[str]) -> None:
    try:
        import make_xlsx
    except ImportError:
        from common import TRACKER_CSV
        print("The Excel view needs the 'openpyxl' package, which isn't installed.\n"
              "  - To enable it:  pip install openpyxl   (then re-run this)\n"
              f"  - Meanwhile, the tracker still works fully as a spreadsheet:\n"
              f"    open {TRACKER_CSV} in Excel, Google Sheets, or Numbers.")
        return
    make_xlsx.build()


def cmd_contact(_args: list[str]) -> None:
    import fill_contact
    fill_contact.fill()


COMMANDS = {
    "intake": lambda a: cmd_intake(a),
    "daily": cmd_daily,
    "review": cmd_review,
    "queue": cmd_queue,
    "applied": cmd_applied,
    "report": cmd_report,
    "xlsx": cmd_xlsx,
    "contact": cmd_contact,
    "card": cmd_card,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return
    cmd = sys.argv[1]
    args = sys.argv[2:]
    fn = COMMANDS.get(cmd)
    if not fn:
        print(f"Unknown command: {cmd}\n")
        print(__doc__)
        return
    fn(args)


if __name__ == "__main__":
    main()
