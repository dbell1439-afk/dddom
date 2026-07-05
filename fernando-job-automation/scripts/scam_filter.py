"""
scam_filter.py — strict scam/spam/fake-posting filter.

Assigns a Scam Risk Rating (Low/Medium/High/Reject) by summing rule weights
against the job text, minus legitimacy signal boosts.
"""
from __future__ import annotations

from common import load_scam_filters, load_target_companies, find_patterns


def _rating_for_weight(weight: int, thresholds: dict) -> str:
    for name in ("Reject", "High", "Medium", "Low"):
        band = thresholds[name]
        if band["min"] <= weight <= band["max"]:
            return name
    return "Low"


def score_scam(job: dict) -> dict:
    """
    Evaluate a normalized job dict. Uses job['raw_text'] if present, otherwise
    concatenates the structured text fields. Returns scam scoring fields.
    """
    filters = load_scam_filters()
    text = job.get("raw_text") or " ".join(
        str(job.get(k, "")) for k in (
            "job_title", "company", "location", "salary_range",
            "application_url", "required_experience",
        )
    ) + " " + " ".join(job.get("responsibilities", []) or [])

    weight = 0
    flags: list[str] = []

    rule_groups = (
        filters["hard_reject_rules"],
        filters["high_risk_rules"],
        filters["medium_risk_rules"],
    )
    for group in rule_groups:
        for rule in group:
            hits = find_patterns(text, rule.get("patterns", []))
            if hits:
                weight += rule["weight"]
                flags.append(f"{rule['id']}: {rule['description']}")

    # legitimacy boosts
    boosts = filters.get("legit_signal_boosts", {}).get("rules", [])
    url = (job.get("application_url") or "").lower()
    companies = load_target_companies()
    known_domains: list[str] = []
    for group_key, group in companies.items():
        if isinstance(group, list):
            for c in group:
                careers = (c.get("careers") or "") if isinstance(c, dict) else ""
                if careers:
                    dom = careers.replace("https://", "").replace("http://", "").split("/")[0]
                    known_domains.append(dom)

    for boost in boosts:
        if boost["id"] == "known_employer_domain":
            if any(dom and dom in url for dom in known_domains):
                weight += boost["weight"]
                flags.append("legit: application URL matches a known employer domain")
        elif boost["id"] == "ats_portal":
            if find_patterns(url, boost.get("patterns", [])):
                weight += boost["weight"]
                flags.append("legit: hosted on a recognized ATS portal")
        elif boost["id"] == "clear_salary_band":
            if job.get("salary_min_usd") and job.get("salary_max_usd"):
                weight += boost["weight"]
                flags.append("legit: concrete salary band provided")

    weight = max(weight, 0)
    rating = _rating_for_weight(weight, filters["risk_thresholds"])
    auto_reject = rating in filters.get("auto_reject_ratings", [])

    return {
        "scam_weight": weight,
        "scam_risk": rating,
        "scam_flags": flags,
        "scam_auto_reject": auto_reject,
    }
