---
trigger: always_on
---

# Workspace rules: cp51

## Task protocol
- Your work is defined solely by tasks/currenttask.md. If it is missing, empty, or self-contradictory, stop and ask; never infer a task.
- Do exactly what currenttask.md describes, nothing beyond it.
- Fresh session, no memory: assume you know nothing beyond these rules, tasks/currenttask.md, and the repo contents. tasks/worklog.md is the project history.
- If the environment does not match the task file's assumptions (runtime version, missing tool, unexpected files), stop and ask before adapting code or configuration.
- Never modify README.md, docs/, PROJECT-INSTRUCTIONS.md, or tasks/currenttask.md unless the task file itself directs it.
- No dependencies beyond requirements.txt without asking.

## Worklog is part of the task, not optional
- A task is NOT complete until its entry exists in tasks/worklog.md. No entry means the task failed its definition of done, regardless of what else was built.
- Write the entry BEFORE the task's final commit, so the commit contains it. One entry per task, template at the top of the file, appended at the bottom, never editing prior entries.
- If a task ends early for any reason (blocked, partial, owner halted it, session ending), write the entry first with Outcome: blocked or partial. Ending a session without an entry is never acceptable.
- Entries contain no defendant names, no docket text, and no em dashes.
- Before starting any task, read the last worklog entry. If the previous task has no entry, tell the owner before doing anything else.

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