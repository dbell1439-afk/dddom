"""
weekly_report.py — generate the weekly strategy report from the tracker + jobs store.

Writes outputs/weekly_report_<date>.md.
"""
from __future__ import annotations

import datetime as _dt
from collections import Counter

from common import today, OUTPUTS_DIR, ensure_dirs, load_jobs_store
from tracker import read_rows


def _category(title: str) -> str:
    t = title.lower()
    buckets = [
        ("Phlebotomy / Donor", ["phlebotom", "donor", "specimen collection"]),
        ("Specimen Processing / Accessioning", ["specimen processing", "accessioning"]),
        ("Lab Operations / Supervisor", ["lab supervisor", "lab manager", "laboratory operations", "operations coordinator", "lab coordinator"]),
        ("Pathology / Cytology / Histology", ["pathology", "cytology", "histology"]),
        ("Clinical Research", ["clinical research", "research coordinator", "research assistant", "clinical trial"]),
        ("Clinical / Lab Data", ["clinical data", "data coordinator", "data abstraction"]),
        ("QA / QC", ["quality assurance", "quality control", "qa ", "qc "]),
        ("Teaching / Instructor", ["instructor", "adjunct", "tutor", "faculty"]),
    ]
    for name, keys in buckets:
        if any(k in t for k in keys):
            return name
    return "Other"


def generate() -> str:
    ensure_dirs()
    rows = read_rows()
    jobs = load_jobs_store()
    week_ago = (_dt.date.today() - _dt.timedelta(days=7)).isoformat()

    reviewed = len(rows)
    rejected_scam = sum(1 for r in rows if r.get("Scam Risk") in ("High", "Reject"))
    rejected_cred = sum(1 for j in jobs if j.get("credential_barrier") == "Hard")
    applied = sum(1 for r in rows if r.get("Status") == "Applied" or r.get("Date Applied"))
    followups = sum(1 for r in rows if r.get("Status") == "Follow-Up Sent")
    interviews = sum(1 for r in rows if r.get("Status") in ("Interview Requested", "Interview Completed"))
    offers = sum(1 for r in rows if r.get("Status") == "Offer")

    # traction by category (applied or advanced)
    advanced = [r for r in rows if r.get("Status") in
                ("Applied", "Follow-Up Sent", "Recruiter Contacted",
                 "Interview Requested", "Interview Completed", "Offer")]
    cat_counter = Counter(_category(r.get("Job Title", "")) for r in advanced)
    company_counter = Counter(
        r.get("Company", "") for r in rows
        if r.get("Status") not in ("Rejected by Filter",) and r.get("Company")
    )

    lines = [
        f"# Weekly Strategy Report — {today()}",
        f"_Covering activity through {today()} (rolling)._\n",
        "## Funnel snapshot",
        f"- Jobs reviewed (in tracker): **{reviewed}**",
        f"- Rejected as spam/scam: **{rejected_scam}**",
        f"- Rejected due to hard credential barrier: **{rejected_cred}**",
        f"- Applied: **{applied}**",
        f"- Follow-ups sent: **{followups}**",
        f"- Interviews (requested/completed): **{interviews}**",
        f"- Offers: **{offers}**\n",
        "## Best-performing role categories (by advanced applications)",
    ]
    if cat_counter:
        for cat, n in cat_counter.most_common():
            lines.append(f"- {cat}: {n}")
    else:
        lines.append("- No applications advanced yet — focus this week on the apply-now queue.")

    lines.append("\n## Companies with the most suitable openings tracked")
    if company_counter:
        for comp, n in company_counter.most_common(8):
            lines.append(f"- {comp}: {n}")
    else:
        lines.append("- None tracked yet.")

    lines += [
        "\n## Recommended resume changes",
        "- Mirror the exact keywords from this week's apply-now postings (see each job card).",
        "- If a category keeps scoring high, promote its resume version to your default.",
        "- Keep the WES-verified foreign degree line near the top for research/lab roles.",
        "\n## Recommended certification / training steps",
        "- Complete CITI GCP + Human Subjects (free/low-cost) to unlock more clinical-research roles.",
        "- Keep BLS/CPR current; add HIPAA + OSHA refreshers if any posting requires them.",
        "- Consider a phlebotomy-instructor credential to open teaching roles.",
        "- Revisit AAB only with a structured study plan; it is NOT a gate for most target roles.",
        "\n## Next-week application targets",
    ]
    # suggest top open jobs not yet applied
    open_apply = [j for j in jobs if j.get("decision") == "Apply"]
    open_apply.sort(key=lambda j: (j.get("probability_score", 0), j.get("fit_score", 0)), reverse=True)
    for j in open_apply[:8]:
        lines.append(f"- {j['job_title']} @ {j['company']} "
                     f"(fit {j['fit_score']}, prob {j['probability_score']}) — {j['recommendation']}")
    if not open_apply:
        lines.append("- Import more postings into job_posts/ and run `python3 jobbot.py daily`.")

    out = OUTPUTS_DIR / f"weekly_report_{today()}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return str(out)


if __name__ == "__main__":
    print(generate())
