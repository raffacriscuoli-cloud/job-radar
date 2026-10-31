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

## 1. Load the queue and the facts

1. `ArtifactData` `query` on collection `jobs` with `where: [["status","==","postular"]]`. Skip jobs whose `applyNote` starts with "Needs you" unless Raffaello says he resolved it.
2. `get` `config/applicant` — contact details and standard answers (salary $200,000, start immediately, U.S. citizen, no sponsorship, the `eeo` answers for voluntary self-identification, FINRA status, the `needsYou` list).
3. `get` `config/resume` — his factual resume. This and `config/applicant` are the **only** sources of truth about him.
4. Tell him in one line how many jobs are in the queue, then start. Process them highest `score` first.

## 2. For each job

### a. Tailor the resume
1. Open the job `url` in a new Chrome tab and read the full description.
2. Fill `resume_template.html` (in this skill's folder) from `config/resume`, tailored to this job:
   - Rewrite the headline and summary toward the role, and order bullets, projects and skill groups by relevance. Mirror the posting's own keywords where they are true for him.
   - Keep it to **one page**. Drop the least relevant bullets rather than shrinking the font.
   - **Never invent or inflate**: no new employers, titles, dates, numbers, licenses, tools or responsibilities. Rewording and reordering only.
3. Save to `~/Documents/Job Radar/<Company> - <Title>/Raffaello Criscuoli - Resume.html` and print it to PDF next to it:
   ```bash
   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu --no-pdf-header-footer --print-to-pdf="<folder>/Raffaello Criscuoli - Resume.pdf" "file://<folder>/Raffaello Criscuoli - Resume.html"
   ```
   Open the PDF once and check it is one page and nothing is clipped.

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
