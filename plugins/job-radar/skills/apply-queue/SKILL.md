---
name: apply-queue
description: Apply to every job in Raffaello's Job Radar apply queue using Claude in Chrome — tailors an English resume per job, fills the application in English and submits it, then records the result on the dashboard. Use when he says "apply to my queue", "run the application agent" or "postula a mi cola".
---

# Apply queue

Raffaello Criscuoli's application agent. It works through the jobs he marked **Apply** on his Job Radar dashboard and applies to each one in his own Chrome.

- Dashboard: https://claude.ai/artifact/F5xUnH7fYTGH5pTxERPNLX
- Data lives in the dashboard's database; read and write it with the `ArtifactData` tool, always passing that URL.
- Browser: Claude in Chrome (`mcp__claude-in-chrome__*`). Load the `chrome-browser` skill before the first browser step.

**Everything that goes to an employer is in English**: resume, form answers, free-text fields, cover letters. Talk to Raffaello in Spanish.

He chose **fully automatic** submission: do not ask before pressing Submit when the application is complete and every answer is truthful and sourced. The safety rules below still apply and override speed.

## 0. Preflight (every run)
Check these before touching the queue, and if one fails tell Raffaello in Spanish exactly what to do, then stop:
- `ArtifactData` is available (it comes with signing in to Claude Code with his claude.ai account). If not: "Inicia sesión en Claude Code con tu cuenta de claude.ai".
- Claude in Chrome tools are available. If not: "Instala o activa la extensión Claude in Chrome y conéctala a Claude Code".
- `python3 --version` works. If not: "Ejecuta `xcode-select --install` en la Terminal".
- Google Chrome is installed at `/Applications/Google Chrome.app` (or `CHROME_PATH` is set) so `render_resume.py` can print PDFs.

## 1. Load the queue and the facts

1. `ArtifactData` `query` on collection `jobs` with `where: [["status","==","postular"]]`. Jobs with an `ats` block (public Greenhouse, Lever or Ashby forms) are applied automatically by the cloud applicator every morning: take them here only when their `applyNote` starts with "Needs you" (for example a CAPTCHA the cloud could not pass) or Raffaello asks. Otherwise skip jobs whose `applyNote` starts with "Needs you" unless he says he resolved it.
2. `get` `config/applicant` — contact details and standard answers (salary $200,000, start immediately, U.S. citizen, no sponsorship, the `eeo` answers for voluntary self-identification, FINRA status, the `needsYou` list).
3. `get` `config/resume` — his factual resume. This and `config/applicant` are the **only** sources of truth about him.
4. Tell him in one line how many jobs are in the queue, then start. Process them highest `score` first.

## 2. For each job

### a. Tailor the resume
1. Open the job `url` in a new Chrome tab and read the full description.
2. Write a tailored copy of `config/resume` as JSON (same fields) to
   `~/Documents/Raffa-Jobs/applications/<Company> - <Title>/resume.json`, following `config/resume.positioning`, `rules` and `style`:
   - Rewrite `headline` and `summary` toward the role; order `experience` bullets, `projects` and `skills` groups by relevance; mirror the posting's keywords and `atsKeywords` only where true.
   - Fit **one page**: set `"onePage": true` (compact layout). Summary at most 3 lines (~60 words). The two most relevant roles get 3–4 bullets of at most ~28 words each; keep a bullet only for older roles that matter to this job and list the rest as title, company and dates only; at most 1–2 projects; at most 3 skill groups of ~7 chips. Drop the least relevant content; never change the design.
   - **Never invent or inflate**: no new employers, titles, dates, numbers, licenses, tools or responsibilities. Rewording, reordering and trimming only.
   - Leave out `rules`, `positioning`, `style`, `pending`, `atsKeywords` and `updatedAt` from the copy.
3. Render it with this skill's design system (IBM Plex, cobalt accent, ATS-safe single column):
   ```bash
   python3 "<this skill's folder>/render_resume.py" "<folder>/resume.json" "<folder>/Raffaello Criscuoli - Resume.pdf"
   ```
   It finds Chrome automatically on macOS. Open the PDF once: it must be one page with nothing clipped; if it spills onto page two, trim and render again.

### b. Apply
1. Press the posting's Apply button. Prefer the company's own application over LinkedIn Easy Apply when both exist.
2. Fill every field from `config/applicant` and the tailored resume. Upload the tailored PDF wherever a resume is requested. If the browser tools cannot attach a local file, ask Raffaello to attach `<folder>/Raffaello Criscuoli - Resume.pdf` himself, wait, then continue.
3. Cover letter: only when the form **requires** one. Then write a short (≤200 words), specific letter in English from the same facts, save it as PDF in the same folder, and attach it. Leave optional cover-letter fields empty.
4. Screening questions: answer in English, concisely, from the facts only. Salary fields → 200000 (or the free-text answer). Start date → immediately.
   Voluntary self-identification (race, ethnicity, gender, veteran, disability): use `config/applicant.eeo` exactly; anything it doesn't cover → "Decline to self-identify".
5. Submit, then confirm the confirmation page or email. Take note of what it says.

### c. Record the result
- **Submitted**: `update` the job (pin `if_version` to the version you read) with `status: "postulada"`, `appliedAt` (ISO UTC now), `appliedVia` (e.g. "Greenhouse", "Workday", "LinkedIn Easy Apply"), `resumeFile` (local PDF path), and remove any `applyNote` with `{"__delete__": true}`.
- **Blocked**: leave `status: "postular"` and set `applyNote` to one line starting with "Needs you:" that says exactly what he must do (e.g. "Needs you: sign in to Workday at jpmc.fa.oraclecloud.com, then run the agent again"). Move on to the next job.

## 3. Stop and mark "Needs you" — never guess
- Anything in `config/applicant.needsYou`: logging in or creating an account, criminal/credit/regulatory disclosures (U4/U5, complaints), references, assessments or video interviews, attestations beyond "the information is accurate".
- Any question whose truthful answer is not in `config/applicant` or `config/resume`.
- A posting that is closed, a duplicate of an application already sent, or that asks for payment or sensitive documents (SSN, passport, bank details) at application time — mark it and skip.
- Never type a password, never solve a CAPTCHA, never change account settings, never message recruiters, never accept terms beyond the application's own submission consent.

## 4. Finish
Reply in Spanish with a short table: company · role · result (Submitted / Needs you + reason). Mention where the PDFs are saved.
