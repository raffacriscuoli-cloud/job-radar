# Daily search agent

Runs every day at 6:47 a.m. (America/New_York) as a Claude Code scheduled task in the cloud environment. It reads the
search profile from the dashboard database, reads job-alert emails from Gmail (LinkedIn, Glassdoor, Indeed),
runs `search/radar_search.py`, scores every new job against Raffaello's background and writes the best ones to the
dashboard. The scheduled task carries the Gmail connector; it only reads alert emails and never sends, labels or
deletes anything.

The scheduled task keeps its own copy of the script in the dashboard database (`config/agent.script`) because it
starts from a fresh container with no repository attached. **This repository is the source of truth:** after
changing `search/radar_search.py`, ask Claude to sync it to `config/agent.script`.

Network allowlist the environment needs: `www.linkedin.com`, `linkedin.com`, `boards-api.greenhouse.io`,
`api.lever.co`, `api.ashbyhq.com` (plus `apis.indeed.com` for Indeed). Setup script: `pip install -q python-jobspy`.
