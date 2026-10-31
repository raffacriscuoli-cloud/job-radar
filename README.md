# Job Radar

Raffaello Criscuoli's personal job search system: a daily search agent, a dashboard to triage jobs, and an
application agent that applies with a tailored English resume.

**Dashboard:** https://claude.ai/artifact/F5xUnH7fYTGH5pTxERPNLX (private)

## How it fits together

```
LinkedIn (JobSpy) ─┐                                                              ┌─► Cloud applicator (7:43 a.m.)
Greenhouse / Ashby ├─► Daily search agent ─► Dashboard database ─► you press Apply ┤   Greenhouse · Lever · Ashby forms
Lever, Gmail alerts┘   (cloud, 6:47 a.m.)     jobs · config · runs                 └─► apply-queue skill (your Mac)
                                                                                       LinkedIn, Workday, bank portals
```

| Path | What it is |
|---|---|
| `dashboard/job-radar.html` | The dashboard page, published as a claude.ai artifact |
| `search/radar_search.py` | Collects jobs from LinkedIn (public listings via JobSpy) and the Greenhouse, Ashby and Lever job-board APIs |
| `agents/daily-search.md` | How the daily scheduled search runs |
| `agents/cloud-apply.md` | Instructions of the daily cloud applicator (also stored in the scheduled task) |
| `apply/apply_ats.js` | Reads and submits public Greenhouse, Lever and Ashby application forms with headless Chrome |
| `plugins/job-radar/skills/apply-queue/` | The application agent (Claude Code skill), the resume design system (`resume.css`, fonts) and `render_resume.py` |
| `resume/` | Master resume (JSON + PDF) and the design system guide (`DESIGN.md`) |

## Dashboard database

| Document | Holds | Edited by |
|---|---|---|
| `config/profile` | Roles, pay, cities, industries, search keywords, Chilean companies, background, interests | You, on the dashboard's Search profile tab |
| `config/agent` | Search script and source list | Claude |
| `config/applicant` | Standard answers for application forms | Claude, on request |
| `config/resume` | Factual resume used to tailor each application | Claude, on request |
| `config/seen` | Jobs already evaluated, so they aren't proposed twice | Daily agent |
| `jobs/*` | Scored jobs and their status (new, saved, apply queue, applied, dismissed) | Daily agent and you |
| `runs/*` | One log entry per daily search | Daily agent |
| `applyRuns/*` | One log entry per cloud application run | Cloud applicator |

## Install the application agent on your Mac

In Claude Code:

```
/plugin marketplace add raffacriscuoli-cloud/job-radar
/plugin install job-radar@job-radar
```

Then install the Claude in Chrome extension, open Claude Code and say **"apply to my queue"**.

## Run the search by hand

```bash
pip install python-jobspy
python3 search/radar_search.py profile.json known_ids.json candidates.json
```

`profile.json` is `config/agent` merged with `config/profile`; `known_ids.json` is a JSON list of job ids to skip.

## Network allowlist for the cloud applicator

The cloud environment must allow the application forms: `job-boards.greenhouse.io`, `boards.greenhouse.io`,
`job-boards.cdn.greenhouse.io`, `jobs.lever.co`, `jobs.ashbyhq.com`, `cdn.ashbyprd.com`, `www.google.com`,
`www.gstatic.com`, `www.recaptcha.net` (CAPTCHA scripts), plus `github.com` to clone this repository.
