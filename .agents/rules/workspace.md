---
trigger: always_on
---

# Workspace rules: cp51

## Task protocol
- Your work is defined solely by currenttask.md in the repo root. If it is missing, empty, or self-contradictory, stop and ask; never infer a task.
- Do exactly what currenttask.md describes, nothing beyond it. When the task is complete or you are blocked, append an entry to worklog.md (format at the top of that file) and stop.
- Fresh session, no memory: assume you know nothing beyond these rules, currenttask.md, and the repo contents. worklog.md is the project history if you need it.
- Never modify README.md, docs/, PROJECT-INSTRUCTIONS.md, or currenttask.md unless currenttask.md itself directs it. worklog.md is append-only.
- No dependencies beyond requirements.txt without asking.

## The live portal is off limits by default
- Never contact the Pennsylvania UJS portal unless the owner explicitly directs that specific run: no Playwright sessions, no test fetches, no connectivity checks, no browser agent visits. Writing scraper code is fine; executing it against the portal is a separate, owner directed event.
- When a run is directed, the MIN_DELAY to MAX_DELAY randomized delay is always active and cached dockets are never refetched.

## Privacy is structural
- Defendant names never appear in the database, logs, console output, fixtures, committed files, commit messages, or worklog entries. A person is represented only by the salted hash.
- Never read, generate, or print real values in .env, including DEFENDANT_HASH_SALT. Copy .env.example into place and tell the owner which values to set themselves.
- Never commit anything under data/ except data/lookups/. Test fixtures that mimic dockets are synthetic or fully redacted.

## Style
- No em dashes anywhere: code, comments, docstrings, YAML, commit messages, worklog entries. Use periods, commas, parentheses, or colons.
- Commit each logical chunk with a clear message. Commits and pushes go through the command approval flow.
- Leave a brief comment where a design choice is not obvious.