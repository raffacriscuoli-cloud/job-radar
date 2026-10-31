# Resume design system — "Ledger"

Banking-grade restraint with an engineering voice: the layout reads like a private-bank document, and the
metadata (dates, contact, section labels) is set in a monospace face, the way a terminal or a ledger would show it.

## Tokens

| Token | Value | Use |
|---|---|---|
| `--ink` | `#0E1726` | Name, role titles, chip text |
| `--body` | `#2A3442` | Running text |
| `--muted` | `#5B6676` | Companies, dates, secondary text |
| `--rule` | `#D9DEE5` | Hairlines and separators |
| `--accent` | `#1D4ED8` | Headline, section labels, bullet markers, header bar |
| `--accent-soft` | `#EEF2FB` | Skill chip fill |

**Type:** IBM Plex Sans (400/500/600) for reading; IBM Plex Mono (400/500) for dates, contact and labels.
Body 9.3pt (8.85pt in one-page mode), name 23pt, section labels 7.6pt mono uppercase with 0.16em tracking.
Fonts are embedded in the PDF (SIL Open Font License, see `plugins/job-radar/skills/apply-queue/fonts/OFL.txt`).

## Rules

- **One reading column.** Applicant tracking systems extract text top to bottom; no sidebars or text in images.
- **One accent.** Cobalt marks structure only (labels, markers, the short bar under the header), never body text.
- **Metadata in mono.** Dates, locations and contact details always use the mono face and the muted color.
- **Skills as chips**, grouped, most relevant group first.
- **Master vs tailored.** `resume/resume.json` is the full master (two pages). Tailored applications set
  `"onePage": true`, which switches to the compact layout, and trim content to fit one page.

## Files

| Path | What it is |
|---|---|
| `resume/resume.json` | Master resume data (mirror of the dashboard's `config/resume`) |
| `resume/Raffaello Criscuoli - Resume.pdf` | Master resume, rendered |
| `plugins/job-radar/skills/apply-queue/resume.css` | The design system as CSS |
| `plugins/job-radar/skills/apply-queue/render_resume.py` | Renders any resume JSON to HTML + PDF with headless Chrome |

Render the master: `python3 plugins/job-radar/skills/apply-queue/render_resume.py resume/resume.json "resume/Raffaello Criscuoli - Resume.pdf"`
