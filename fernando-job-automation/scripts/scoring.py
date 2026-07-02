"""
scoring.py — weighted 0-100 fit score, probability-of-success score,
and recommendation category for a normalized job.

Weights (max):
  Credential alignment ....... 20
  Relevant experience ........ 20
  Transferable skills ........ 15
  Local/remote feasibility ... 10
  Compensation improvement ... 10
  Bilingual advantage ........  5
  Certification feasibility .. 10
  Probability of interview ... 10
  --------------------------------
  Total ...................... 100

Deductions are applied on top for hard barriers, sales roles, commute, low pay, etc.
"""
from __future__ import annotations

import re
from common import load_profile

# Keyword sets used for experience / skill / role matching
_HIGH_PROB_TITLES = [
    "phlebotom", "specimen processing", "accessioning", "lab operations",
    "laboratory operations", "pathology", "cytology", "histology",
    "clinical research assistant", "clinical research coordinator",
    "research coordinator", "research assistant", "lab coordinator",
    "clinical data", "data coordinator", "quality control", "quality assurance",
    "instructor", "specimen", "donor",
]
_LOW_PROB_TITLES = [
    "senior scientist", "principal scientist", "cytotechnologist",
    "medical technologist", "medical laboratory scientist", "clinical research associate",
    "lab director", "laboratory director", "director of",
]

_EXPERIENCE_TERMS = [
    "specimen", "phlebotomy", "venipuncture", "laboratory", "clinical",
    "cytology", "pathology", "histology", "quality", "compliance", "sop",
    "protocol", "training", "supervis", "coordinat", "accession",
    "research", "documentation", "patient",
]
_SALES_TERMS = ["commission", "quota", "sales target", "cold call", "b2b sales", "outside sales", "territory sales"]


def _score_credential_alignment(job: dict) -> tuple[float, str]:
    barrier = job.get("credential_barrier", "None")
    if barrier == "Hard":
        return 2.0, "Hard credential barrier Fernando lacks (minimal alignment)"
    if barrier == "Soft":
        return 13.0, "Credential mentioned but pathway/equivalency/preferred — workable"
    return 18.0, "No blocking credential requirement"


def _score_experience(job: dict) -> tuple[float, str]:
    text = (job.get("raw_text") or job.get("required_experience", "")).lower()
    hits = sum(1 for t in _EXPERIENCE_TERMS if t in text)
    score = min(20.0, 4 + hits * 2.0)
    return score, f"{hits} direct experience-term matches"


def _score_transferable(job: dict) -> tuple[float, str]:
    profile = load_profile()
    text = (job.get("raw_text") or "").lower()
    skills = profile["transferable_skills"]
    hits = 0
    for s in skills:
        head = s.split()[0].lower()
        if head in text:
            hits += 1
    score = min(15.0, 5 + hits * 1.5)
    return score, f"{hits} transferable-skill signals present"


def _score_feasibility(job: dict) -> tuple[float, str]:
    profile = load_profile()
    mode = job.get("work_mode", "Unknown")
    loc = (job.get("location") or "").lower()
    if mode == "Remote":
        return 10.0, "Remote (U.S.) — fully feasible"
    if mode == "Hybrid":
        return 8.0, "Hybrid — feasible if within commute range"
    pref = [p.lower().split(" (")[0] for p in profile["location"]["preferred_geography"]]
    if any(city in loc for city in pref):
        return 10.0, "On-site within preferred Tampa Bay geography"
    if "fl" in loc or "florida" in loc:
        return 6.0, "In Florida but outside core preferred area — check commute"
    if mode == "On-site":
        return 3.0, "On-site, location unclear or outside area"
    return 5.0, "Work mode/location unclear"


def _score_comp(job: dict) -> tuple[float, str]:
    profile = load_profile()
    base = profile["salary_goals"]["current_baseline_usd"]
    target_min = profile["salary_goals"]["target_min_usd"]
    hi = job.get("salary_max_usd")
    lo = job.get("salary_min_usd")
    if not hi and not lo:
        return 5.0, "No salary listed — neutral"
    top = hi or lo
    if top >= target_min:
        return 10.0, f"Meets/exceeds ${target_min:,} target"
    if top >= base * 1.1:
        return 7.0, "Above current pay but below target"
    if top >= base * 0.95:
        return 4.0, "Roughly lateral to current pay"
    return 1.0, "Below current pay"


def _score_bilingual(job: dict) -> tuple[float, str]:
    text = (job.get("raw_text") or "").lower()
    if re.search(r"portuguese", text):
        return 5.0, "Portuguese explicitly valued — strong edge"
    if re.search(r"bilingual|spanish", text):
        return 4.0, "Bilingual/Spanish valued"
    if re.search(r"diverse|multicultural|patient population", text):
        return 2.0, "Diverse/patient-facing — bilingual helps"
    return 1.0, "Bilingual not specifically leveraged"


def _score_cert_feasibility(job: dict) -> tuple[float, str]:
    barrier = job.get("credential_barrier", "None")
    text = (job.get("raw_text") or "").lower()
    obtainable = ["citi", "gcp", "hipaa", "osha", "bls", "phlebotomy certification"]
    if barrier == "Hard":
        return 1.0, "Requires a certification that is a hard barrier"
    if any(o in text for o in obtainable):
        return 10.0, "Any needed certs are quickly obtainable (CITI/GCP/HIPAA/OSHA/BLS)"
    if barrier == "Soft":
        return 7.0, "Soft cert expectation — achievable pathway"
    return 9.0, "No certification obstacle"


def _score_interview_prob(job: dict) -> tuple[float, str]:
    title = (job.get("job_title") or "").lower()
    if any(t in title for t in _HIGH_PROB_TITLES):
        return 9.0, "Title is in a high-probability category for Fernando"
    if any(t in title for t in _LOW_PROB_TITLES):
        return 3.0, "Title is a lower-probability/credentialed category"
    return 6.0, "Neutral interview probability"


def _deductions(job: dict) -> tuple[float, list[str]]:
    profile = load_profile()
    text = (job.get("raw_text") or "").lower()
    title = (job.get("job_title") or "").lower()
    deduct = 0.0
    notes: list[str] = []

    if job.get("credential_barrier") == "Hard":
        deduct += 25
        notes.append("-25 hard-required credential/license Fernando lacks with no pathway")

    if any(s in text for s in _SALES_TERMS) or "sales" in title:
        deduct += 12
        notes.append("-12 heavy sales/commission component")

    # commute
    mode = job.get("work_mode", "Unknown")
    loc = (job.get("location") or "").lower()
    pref = [p.lower().split(" (")[0] for p in profile["location"]["preferred_geography"]]
    if mode == "On-site" and loc and not any(c in loc for c in pref) and ("fl" not in loc and "florida" not in loc):
        deduct += 8
        notes.append("-8 on-site and likely beyond daily commute")

    # low pay
    base = profile["salary_goals"]["current_baseline_usd"]
    top = job.get("salary_max_usd") or job.get("salary_min_usd")
    if top and top < base * 0.95 and not profile["salary_goals"]["strategic_lateral_ok"]:
        deduct += 6
        notes.append("-6 salary below current pay")

    # vague posting
    if len(job.get("responsibilities") or []) == 0 and len(job.get("raw_text") or "") < 300:
        deduct += 5
        notes.append("-5 vague/thin posting")

    # seniority mismatch
    if any(t in title for t in ["senior", "principal", "director", "manager ii", "iii"]) and "assistant" not in title:
        if job.get("credential_barrier") == "Hard":
            deduct += 4
            notes.append("-4 seniority/credential mismatch")

    return deduct, notes


def score_job(job: dict) -> dict:
    """Compute fit score, probability score, recommendation, and reasoning."""
    components = {}
    reasoning_parts: list[str] = []

    for label, fn in (
        ("credential_alignment", _score_credential_alignment),
        ("relevant_experience", _score_experience),
        ("transferable_skills", _score_transferable),
        ("feasibility", _score_feasibility),
        ("compensation", _score_comp),
        ("bilingual", _score_bilingual),
        ("cert_feasibility", _score_cert_feasibility),
        ("interview_probability", _score_interview_prob),
    ):
        pts, why = fn(job)
        components[label] = round(pts, 1)
        reasoning_parts.append(f"{label}: +{pts:.1f} ({why})")

    subtotal = sum(components.values())
    deduct, deduct_notes = _deductions(job)
    reasoning_parts.extend(deduct_notes)

    fit = max(0.0, min(100.0, subtotal - deduct))

    # Probability of success: weighted toward feasibility, cert, interview prob, and no hard barrier
    prob = (
        components["interview_probability"] * 4.0
        + components["cert_feasibility"] * 2.0
        + components["feasibility"] * 2.0
        + components["credential_alignment"] * 1.0
    )
    prob = max(0.0, min(100.0, prob - deduct))

    rec = _recommendation(fit, job)

    return {
        "fit_score": round(fit, 1),
        "probability_score": round(prob, 1),
        "score_components": components,
        "score_deductions": round(deduct, 1),
        "recommendation": rec,
        "decision": "Apply" if rec not in ("Do not apply",) and job.get("scam_risk") not in ("High", "Reject") and job.get("credential_barrier") != "Hard" else "Do Not Apply",
        "reasoning": " | ".join(reasoning_parts),
    }


def _recommendation(fit: float, job: dict) -> str:
    if job.get("scam_risk") in ("High", "Reject"):
        return "Do not apply"
    if job.get("credential_barrier") == "Hard":
        return "Do not apply"
    if fit >= 85:
        return "Apply immediately"
    if fit >= 70:
        return "Strong match"
    if fit >= 55:
        return "Possible match"
    if fit >= 40:
        return "Weak match"
    return "Do not apply"


# Best resume version routing
def best_resume(job: dict) -> str:
    title = (job.get("job_title") or "").lower()
    text = (job.get("raw_text") or "").lower()
    if any(t in title for t in ["clinical research", "research coordinator", "research assistant", "clinical trial", "clinical data", "data coordinator"]):
        return "clinical_research_resume.md"
    if any(t in title for t in ["lab supervisor", "lab manager", "laboratory operations", "operations coordinator", "specimen processing", "accessioning", "quality"]):
        if "quality" in title or "qa" in title or "qc" in title:
            return "qa_qc_lab_resume.md"
        return "lab_operations_resume.md"
    if any(t in title for t in ["phlebotom", "donor", "specimen collection"]):
        return "phlebotomy_lead_resume.md"
    if any(t in title for t in ["instructor", "adjunct", "tutor", "faculty", "teach"]):
        return "teaching_training_resume.md"
    if any(t in title for t in ["pathology", "cytology", "histology"]):
        return "lab_operations_resume.md"
    return "master_resume.md"
