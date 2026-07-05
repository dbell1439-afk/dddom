# Weekly Report

Two ways to produce it:

## Option 1 — Automatic (recommended)
```
cd fernando-job-automation
python3 scripts/jobbot.py report
```
This reads the tracker + jobs store and writes `outputs/weekly_report_<date>.md` with:
- Funnel snapshot (reviewed / scam-rejected / credential-rejected / applied / follow-ups / interviews / offers)
- Best-performing role categories
- Companies with the most suitable openings
- Recommended resume changes
- Recommended certification/training steps
- Next-week application targets

## Option 2 — Narrative version with Claude
Paste this prompt with the generated report for a written strategy summary:
```
You are a job-search strategist for Fernando Rodrigues. Here is this week's data:
<paste outputs/weekly_report_<date>.md and, if useful, data/application_tracker.csv>

Write a short strategy memo (to Dominique and Fernando) covering:
1. What's working (which role categories are getting traction and why).
2. What to stop doing (low-yield categories or sources).
3. The 5 specific jobs to apply to next week, in order, with the resume version for each.
4. One certification/training action that would most increase interview rates.
5. One resume tweak based on repeated missing keywords.
Keep it under 400 words, practical and encouraging.
```
