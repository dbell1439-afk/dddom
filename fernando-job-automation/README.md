# Fernando's Job Application Automation System

A **local-first, offline** system that helps Fernando Rodrigues find, filter, score,
track, and apply to legitimate, high-probability jobs — without mass-applying, without
scams, and without chasing roles blocked by certifications he doesn't hold.

Built to be run by **Dominique and Fernando** together. No API keys. No accounts. No
data leaves the computer. Everything is plain files you can read and edit.

---

## What it does

1. **Imports** job postings you paste in (URLs, descriptions, or CSV exports).
2. **Filters** scams/spam and roles that hard-require credentials Fernando lacks.
3. **Scores** each job 0–100 for fit and gives a probability-of-success score.
4. **Ranks** everything into a prioritized **application queue** (highest probability first).
5. **Tracks** every application, contact, follow-up, interview, and outcome in a spreadsheet.
6. **Generates** tailored resumes, cover letters, recruiter messages, and interview prep
   (using the prompt templates in `/prompts`).
7. **Reports** weekly on what's working and what to do next.

> ⚠️ It does **not** browse the internet or auto-submit applications. You paste jobs in;
> it does the analysis, prioritization, and paperwork. You click "apply." This keeps it
> safe, honest, and under your control.

---

## One-time setup (5 minutes)

You need **Python 3.9+** (already common on Mac/Windows/Linux).

```bash
cd fernando-job-automation
python3 -m pip install -r requirements.txt      # installs openpyxl (for the Excel file)
```

Then fill in your contact details **once** in `data/contact_info.json` (phone, email,
LinkedIn) and run:

```bash
python3 scripts/jobbot.py contact
```

That stamps them into every resume and the cover-letter template automatically — no need
to edit each file by hand. Re-run it any time you change `contact_info.json`.

That's it.

---

## The daily routine (10–20 minutes)

### Step 1 — Add the jobs you found
For each interesting posting, create a text file in the `job_posts/` folder and paste in
the job. The whole description is best; a URL + a few lines also works.

- Save as `job_posts/anything.txt` (e.g. `job_posts/quest_specimen.txt`).
- Put the application URL on the first line if you have it.
- You can add as many `.txt` files as you like.
- **CSV from LinkedIn/Indeed?** Just drop it in `job_posts/` and use `--csv` in Step 2.

See real examples in `job_posts/examples/`.

### Step 2 — Run the daily pipeline
```bash
python3 scripts/jobbot.py daily
```
(For a CSV export instead: `python3 scripts/jobbot.py daily --csv job_posts/yourfile.csv`)

This imports, de-duplicates, runs the scam filter, runs the credential filter, scores
everything, updates the tracker, and prints your **Top Application Queue**. It also writes
`outputs/application_queue.md` — a clean list of exactly what to apply to, in order.

### Step 3 — Work the queue (apply to the top jobs)
Open `outputs/application_queue.md`. For each "Apply now" job:

1. Note the **Best Resume** it recommends (a file in `/resumes`).
2. Open `prompts/resume_tailoring_prompt.md`, paste it into Claude with the job + that
   resume → get a tailored, ATS-optimized resume.
3. Open `prompts/cover_letter_prompt.md`, paste with the job → get a cover letter; save it
   in `/cover_letters`.
4. Submit the application on the employer's own careers page when possible.
5. Mark it applied so follow-ups get scheduled:
   ```bash
   python3 scripts/jobbot.py applied "Job Title" "Company" resume_file.md cover_file.md
   ```

### Step 4 — Prep for any interview
When a job replies, open `prompts/interview_prep_prompt.md`, paste it with the job, and
get a full ESL-aware prep pack (likely questions, short answers, Portuguese anchors, STAR
stories, and honest scripts for explaining foreign credentials and certification status).

### Step 5 — Update the Excel tracker (optional, anytime)
```bash
python3 scripts/jobbot.py xlsx
```
Opens/rebuilds `data/application_tracker.xlsx` with dropdowns and a live dashboard. You can
also just edit `data/application_tracker.csv` directly in any spreadsheet program.

---

## The weekly routine (once a week)
```bash
python3 scripts/jobbot.py report
```
Writes `outputs/weekly_report_<date>.md`: funnel numbers, best-performing role categories,
top companies, recommended resume/cert changes, and next week's targets. For a narrative
memo, use `prompts/weekly_report_prompt.md`.

---

## All commands

| Command | What it does |
|---|---|
| `python3 scripts/jobbot.py daily` | Full pipeline: import → filter → score → rank → update tracker → write queue. **This is the main one.** |
| `python3 scripts/jobbot.py daily --csv FILE` | Same, importing from a job-board CSV. |
| `python3 scripts/jobbot.py review` | Score the `job_posts/*.txt` and print a full card for each (nothing saved). |
| `python3 scripts/jobbot.py queue` | Show the current prioritized application queue. |
| `python3 scripts/jobbot.py card "Title" "Company"` | Print the detailed output card for one job. |
| `python3 scripts/jobbot.py applied "Title" "Company" [resume] [cover]` | Mark applied; auto-sets a 3-day follow-up. |
| `python3 scripts/jobbot.py report` | Generate the weekly strategy report. |
| `python3 scripts/jobbot.py contact` | Stamp `data/contact_info.json` into every resume + cover template. |
| `python3 scripts/jobbot.py xlsx` | Rebuild the Excel tracker with dropdowns + dashboard. |

---

## How scoring works (plain English)

**Scam filter** → each job gets **Low / Medium / High / Reject**. High and Reject are
auto-rejected. It flags payment requests, gift-card/crypto/check schemes, Telegram/WhatsApp-
only recruiting, personal-email recruiters, requests for SSN/bank details before an offer,
commission-only roles disguised as clinical, vague postings, and more. Real employer/ATS
domains (Workday, iCIMS, Greenhouse, Lever, Taleo) lower the risk.

**Credential filter** → **None / Soft / Hard**. If a posting *hard-requires* something
Fernando lacks (ASCP MLS/MT, AAB, FL lab license, cytotech cert, RN/MD/PA/PharmD) with **no**
pathway, it's a **Hard** barrier and the job is auto-rejected. If the posting says "or
equivalent experience," "foreign credential accepted," "pending certification," "will train,"
or lists it as preferred → it's **Soft** and still in play.

**Fit score (0–100)** = credential alignment (20) + relevant experience (20) + transferable
skills (15) + location/remote feasibility (10) + compensation improvement (10) + bilingual
advantage (5) + certification feasibility (10) + interview probability (10), minus deductions
for hard barriers, heavy sales, long commute, low pay, or vague postings.

**Recommendation bands:** 85–100 Apply immediately · 70–84 Strong match · 55–69 Possible
(strategic) · 40–54 Weak (save) · below 40 Do not apply.

**Probability score** weights the factors that most predict *getting an interview* for
Fernando specifically (title category, certification feasibility, feasibility, no hard barrier),
so the queue leads with realistic wins, not just prestigious titles.

Want to change the weights or rules? Edit `data/scam_filters.json`,
`scripts/scoring.py`, or `scripts/credential_filter.py` — they're readable and commented.

---

## Folder guide

```
fernando-job-automation/
├── README.md                         ← you are here
├── credential_gap_recommendations.md ← which certs are worth pursuing (ROI table)
├── requirements.txt
├── data/
│   ├── candidate_profile.json        ← the source of truth (edit if facts change)
│   ├── contact_info.json             ← fill once; `jobbot.py contact` stamps resumes
│   ├── scam_filters.json             ← scam/spam rules + weights
│   ├── target_companies.json         ← priority employers + their ATS/careers domains
│   ├── job_sources.json              ← intake formats + normalized job schema
│   ├── application_tracker.csv        ← the tracker (edit in any spreadsheet app)
│   └── application_tracker.xlsx       ← styled tracker with dropdowns + dashboard
├── resumes/                          ← honest master + 5 role-specific resumes
├── cover_letters/                    ← generated letters + a template
├── job_posts/                        ← drop pasted jobs here (.txt); examples/ has samples
├── outputs/                          ← queue, weekly reports, and jobs.json (generated)
├── prompts/                          ← Claude prompt templates (resume, cover, interview, etc.)
└── scripts/                          ← the Python engine (jobbot.py is the entry point)
```

---

## The rules this system enforces (so you don't have to remember them)

- **Never mass-apply.** Work the ranked queue, top-down.
- **Never apply to scams or unclear companies.** Auto-rejected before you see them in the queue.
- **Never fabricate credentials.** Every resume/prompt says: honest positioning only. No fake
  U.S. licenses, certifications, employers, or publications — ever.
- **Don't chase hard-blocked roles.** Jobs that truly require MLS/MT/ASCP or a FL license with
  no pathway are auto-rejected.
- **Prefer employer career pages** over low-quality job-board reposts.
- **Every job comes with a reason** it's worth applying to (or not).
- **Optimize for speed, legitimacy, interview probability, and salary improvement** toward the
  $60k–$90k goal.

---

## Where Fernando's edge is (built into the scoring)

Highest-probability, apply-first categories: **Lead Phlebotomist / Phlebotomy Supervisor,
Specimen Processing / Accessioning Supervisor, Lab Operations Coordinator, Pathology/Cytology
Lab Assistant, Clinical Research Assistant / Coordinator I, Research Lab Coordinator, bilingual
clinical-research support, Phlebotomy instructor, Lab quality/documentation coordinator,
Clinical data coordinator.** His WES-verified biomedical Master's, cytology specialization, lab
leadership, current hospital lead role, and Portuguese/Spanish fluency are his advantages — the
system leads with them.
