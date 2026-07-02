---
trigger: always_on
---

# Workspace rules: phl-sentencing-forecaster

## Scope and sequencing
- Build in the chunks defined in the build roadmap. Finish the current chunk, stop, and report. Do not begin the next chunk, or any piece of it, until directed.
- Follow the build spec exactly where it gives file contents. Propose deviations before making them.
- No dependencies beyond requirements.txt without asking. Analysis libraries arrive in the analysis phase.

## The live portal is off limits by default
- Never contact the Pennsylvania UJS portal unless I explicitly direct that specific run: no Playwright sessions, no test fetches, no connectivity checks, no browser agent visits. Writing scraper code is fine; executing it against the portal is a separate, user directed event.
- When a run is directed, the MIN_DELAY to MAX_DELAY randomized delay is always active and cached dockets are never refetched.

## Privacy is structural
- Defendant names never appear in the database, logs, console output, fixtures, committed files, or commit messages. A person is represented only by the salted hash.
- Never read, generate, or print real values in .env, including DEFENDANT_HASH_SALT. Copy .env.example into place and tell me which values to set myself.
- Never commit anything under data/. Test fixtures that mimic dockets are synthetic or fully redacted.

## Style
- No em dashes anywhere: code, comments, docstrings, commit messages, docs. Use periods, commas, parentheses, or colons.
- Commit each logical chunk with a clear message. Commits and pushes go through the command approval flow.
- Leave a brief comment where a design choice is not obvious.