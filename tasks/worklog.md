# CP51 worklog

Append-only record of every task, one entry per task, newest at the bottom.
Agents: this file and currenttask.md are your only channels. Follow the
template exactly; the owner and every future agent rely on this file as the
sole record of what happened. Never edit or delete prior entries. No em
dashes anywhere in entries.

Entry template:

```
## YYYY-MM-DD: <task name, as titled in currenttask.md>
- Outcome: done | blocked | partial
- Built: <files created or changed, one line each>
- Commands: <each approved command and its one line result>
- Deviations: <none, or exactly what differed from the task file and why>
- Owner items: <actions waiting on the owner, e.g. .env awaiting salt>
- Next agent: <anything the next task needs to know>
```

---

(entries begin below this line)

## 2026-07-02: Phase 1, scaffold CP51
- Outcome: done
- Built:
  - data/raw/, data/interim/, data/processed/, data/lookups/
  - src/acquire/, src/parse/, src/db/, src/analysis/
  - notebooks/, scripts/, tests/
  - src/__init__.py, src/acquire/__init__.py, src/parse/__init__.py, src/db/__init__.py, src/analysis/__init__.py
  - .gitignore
  - requirements.txt
  - .env.example
  - .env (copied from example)
  - src/config.py
  - src/db/schema.py (modified to use Optional for Python 3.9 compatibility)
  - src/db/session.py
  - data/lookups/charge_categories.yaml
  - data/lookups/disposition_map.yaml
  - data/lookups/judge_overrides.yaml
- Commands:
  - `mkdir -p ... && touch ...`: Created skeleton directory tree and package init files.
  - `python3 -m venv ... && source ... && pip install ... && playwright install ... && cp ... && python -m src.db.session`: Set up environment and initialized db. Failed on Python 3.9 runtime type union evaluation.
  - `source .venv/bin/activate && python -m src.db.session`: Successfully initialized database after updating schema.py with typing.Optional.
  - `sqlite3 data/processed/phl.db ".tables"`: Verified that all eight tables exist.
  - `git init && git add . && git commit ... && git remote add ... && git push ...` are the final approved commands pending execution after this entry is written.
- Deviations:
  - Modified src/db/schema.py to use typing.Optional instead of union type operator (X | None) to ensure compatibility with Python 3.9.
- Owner items:
  - Owner must set DEFENDANT_HASH_SALT in .env personally.
- Next agent:
  - The skeleton structure, virtual environment, and database schema are initialized and verified. The repository is ready for acquisition and parser development.

## 2026-07-02: environment repair and fixture acquisition
- Outcome: done
- Built:
  - .vscode/settings.json (updated python interpreter path and automatic terminal activation)
  - .gitignore (appended .vscode/ to ignored paths)
  - scripts/fetch_fixtures.py (created script to fetch docket PDFs, selectors updated to match portal DOM)
  - scripts/fixture_summary.py (created script to analyze docket PDFs for disposition and sentence keywords)
- Commands:
  - `grep -q ...`: Verified that the DEFENDANT_HASH_SALT is set.
  - `python3.13 --version || python3.12 --version`: Checked Python version availability, none found.
  - `brew install python@3.12`: Installed Python 3.12 via Homebrew.
  - `rm -rf .venv && python3.12 -m venv ...`: Attempted rebuild of virtual environment, succeeded but later found to be split.
  - `PYTHONPATH=. python scripts/fetch_fixtures.py --probe`: Sourced venv and ran probe fetch, failed with ModuleNotFoundError.
  - `PYTHONPATH=. python scripts/fetch_fixtures.py --probe`: Probed again with PYTHONPATH set, failed to locate select elements on portal.
  - `PYTHONPATH=. python .../inspect_select.py`: Scratch script ran to inspect portal dropdown selectors.
  - `PYTHONPATH=. python .../inspect_inputs.py`: Scratch script ran to inspect portal inputs, failed on missing label elements.
  - `PYTHONPATH=. python .../inspect_inputs.py`: Rerun scratch script with robust checks, successfully retrieved docket input element details.
  - `PYTHONPATH=. python scripts/fetch_fixtures.py --probe`: Probe fetch succeeded on attempt 2 after updating CSS selectors.
  - `PYTHONPATH=. python scripts/fetch_fixtures.py`: Batch fetch ran in background, fetched and saved 30 PDFs in 56 attempts.
  - `PYTHONPATH=. .venv/bin/python scripts/fixture_summary.py`: Summary check failed due to venv corruption.
  - `rm -rf .venv && ls -la .venv`: Cleaned up corrupted venv directory structure.
  - `python3.12 -m venv .venv && ...`: Cleanly rebuilt virtual environment and installed dependencies.
  - `PYTHONPATH=. .venv/bin/python scripts/fixture_summary.py`: Successfully generated keyword coverage summary across all 31 fetched PDFs.
- Deviations:
  - Selector paths inside fetch_fixtures.py adjusted (using title and name attributes rather than label text) because the portal DOM has no associated label tags for Search By and Docket Number.
  - Sourced venv commands run with PYTHONPATH set to project root to resolve import path mapping.
- Owner items: none
- Next agent:
  - Environment is repaired and active with Python 3.12.13.
  - Playwright and pdfplumber dependencies are correctly configured.
  - Validation set of 31 CP docket sheet PDFs has been successfully acquired in data/raw/ and corresponding metadata is stored in local database.
  - Disposition and sentence keyword coverage summary generated successfully: Nolle Prossed: 1, Withdrawn: 1, Guilty Plea - Negotiated: 16, Guilty Plea - Non-Negotiated: 7, Guilty Plea: 24, Not Guilty: 1, ARD: 1, Confinement: 23, Probation: 25, Jury Trial: 3.

## 2026-07-02: Phase 3, docket sheet parser (backfilled by owner)
- Outcome: done
- Built:
  - src/identity.py (hashing, name normalization, privacy leak assertion)
  - src/parse/helpers.py (dates, length-to-days conversion, grades)
  - src/parse/docket_parser.py (docket sheet PDF to contract JSON)
  - scripts/recon_headers.py, scripts/parse_fixtures.py, scripts/build_audit_pack.py
  - tests/ (helper unit tests)
  - requirements.txt (pytest added, authorized by the task file)
  - .agents/rules/workspace.md (worklog gate added)
  - data/interim/: 31 contract JSON records (local only, gitignored)
- Commands: summarized; the session ended without an entry so the transcript
  is not retained. pytest green; recon run over 31 PDFs; parse_fixtures.py
  parsed 31 of 31 with zero failures (raw_dockets ledger confirms);
  build_audit_pack.py produced the 10 docket audit pack.
  - Owner audit: round one found one wrong docket of 10 (dropped cross-page
    Confinement on CP-51-CR-0000267-2021 seq 1); three fixes applied
    (cross-page sentence collection, decimal quantity support, removal of
    the case-status nulling branch); round two re-checked via diff against
    the v1 pack and passed.
- Deviations:
  - Entry backfilled by the owner; the session ended without writing it. The
    worklog gate now in workspace rules exists to prevent recurrence.
  - to_days extended for decimal quantities as printed on real dockets
    ("11.00 Months 15.00 Days"); verified correct (345/690 for 11 1/2 to 23).
  - Day conversion convention: day = 1, month = 30, year = 360, so 1 Year
    equals 12 Months. Set by the owner in the task file before dispatch;
    tests assert it (1 Year 6 Months = 540).
- Owner items: none
- Next agent:
  - 31 interim JSONs in data/interim/ are the loader input.
  - Loader inventory: add "ARD - County" to disposition_map.yaml; one
    concatenated contempt disposition falls to other by design; 18 null
    dispositions are open charges; 15 sentencing judges, all clean
    "Last, First M." format, no variants; charge_categories.yaml still
    needs its statute-to-category rules.
## 2026-07-02: Phase 4, loader and end to end pipeline
- Outcome: done
- Built:
  - data/lookups/disposition_map.yaml (added ARD - County mapping)
  - data/lookups/charge_categories.yaml (added statute_map block)
  - src/db/load.py (database loader class, resolvers, and stats)
  - scripts/run_pipeline.py (pipeline orchestrator runner)
  - tests/test_load_helpers.py (helper unit tests)
- Commands:
  - `ls data/interim/CP-*.json | wc -l && .venv/bin/python -m pytest tests/ -q && git status -sb && git log --oneline -3`: Preflight checked 31 interim files, 10 passing tests, and git state.
  - `.venv/bin/python -m pytest tests/ -q`: Ran test suite, 15 tests passed.
  - `.venv/bin/python -m src.db.load`: Ran first database load. Verified expected counts: 31 cases, 70 charges, 43 sentence components, 15 judges, 31 defendants.
  - `.venv/bin/python -m src.db.load && PYTHONPATH=. .venv/bin/python scripts/run_pipeline.py && sqlite3 data/processed/phl.db ...`: Ran loader twice and pipeline once. Verified database counts remained identical, proving idempotency.
  - `sqlite3 -header -column data/processed/phl.db "SELECT ..."`: Ran verification queries to report category and judge distributions.
- Deviations: none
- Owner items: none
- Next agent:
  - Database is fully loaded with parsed fixture cases.
  - Idempotency verified.
  - Ready for Phase 5 (analysis or scale up).

## 2026-07-04: Phase 2 scale-up, production collector
- Outcome: done
- Built:
  - src/acquire/portal.py (extracted portal code)
  - src/acquire/enumerate.py (sequence enumeration walk logic)
  - scripts/collect.py (batch collect runner script)
  - tests/test_enumerate.py (unit tests for enumeration)
  - src/config.py (collection window environment setting)
  - .env.example (collection window template variable)
  - scripts/fetch_fixtures.py (refactored to import from portal.py)
  - docs/ROADMAP.md (updated phase statuses and Loader milestone met note)
  - docs/DATABASE.md (updated parse_status value range list)
- Commands:
  - `.venv/bin/python -m pytest tests/ -q && ...`: Preflight ran: 17 tests passed and 31 database ledger cases verified as parsed.
  - `git diff`: Checked local modification details.
  - `.venv/bin/python -c "from src.acquire.portal import fetch_docket_pdf; print('import ok')"`: Succeeded in testing imports.
  - `PYTHONPATH=. .venv/bin/python scripts/collect.py --limit 25`: Ran directed validation batch: 25 lookups, 18 saved, 7 misses, 0 errors.
  - `PYTHONPATH=. .venv/bin/python scripts/collect.py --limit 5`: Ran resume proof: 5 lookups, 5 saved, 0 misses, 0 errors.
  - `PYTHONPATH=. .venv/bin/python scripts/run_pipeline.py`: Parsed and loaded all 54 PDFs: 54 cases, 107 charges, 113 sentence components, 22 judges, 46 defendants.
  - `sqlite3 data/processed/phl.db ...`: Verified ledger contains 54 parsed and 7 not_found cases (61 total rows).
  - `git diff docs/`: Verified documentation changes.
- Deviations: none
- Owner items: none
- Next agent:
  - Collection is hardened, repeatable, and ready to be run by the owner.
  - All unit tests pass, and database is populated with 54 parsed cases.

## 2026-07-04: Phase 2, search-form collector
- Outcome: done
- Built:
  - src/acquire/portal.py (replaced)
  - src/acquire/windows.py (created)
  - tests/test_windows.py (created)
  - scripts/collect.py (replaced)
  - src/db/schema.py (modified to add HarvestWindow table)
- Removed:
  - src/acquire/enumerate.py
  - tests/test_enumerate.py
- Commands:
  - `.venv/bin/python -m pytest tests/ -q && git status -sb`: Preflight checked 23 passing tests and clean git tree.
  - `grep -rn "enumerate" src/ scripts/ tests/`: Verified no references to the enumerate module remain in code.
  - `git rm src/acquire/enumerate.py tests/test_enumerate.py`: Removed retired collector and test files.
  - `.venv/bin/python -m pytest tests/ -q && ...`: Ran offline verification suite, confirming pytest green (23 passed), database schema updated with harvest_windows table, database case count (54) and judge count (22) unchanged, weekly window dry-run correct, and scripts.collect import successful.
- Deviations: none
- Owner items: none
- Next agent:
  - The weekly search-form production collector has been successfully built and offline-verified without contacting the portal. The database is prepared with the harvest_windows resume ledger. The owner runs the first live directed validation.

## 2026-07-04: Phase 2, collector live-run fixes
- Outcome: done
- Built:
  - scripts/collect.py (two live-run corrections in the frozen collector logic)
- Corrections:
  - Docket cell index: harvest read the docket number from cell 0 (cells.first), but the portal results grid puts the docket number in cell index 2. Every row failed the CP-51-CR match and was skipped, so weeks reported a large total_rows but 0 CP-51-CR and saved nothing. Changed the read to cells.nth(2), and tightened the empty-row guard from cells.count() == 0 to cells.count() <= 2 so the guard matches the cell being read.
  - ISO date format: the FiledStartDate and FiledEndDate fields are <input type="date"> and require ISO yyyy-mm-dd. run_search fills both with strftime("%Y-%m-%d") rather than mm/dd/yyyy.
- Root cause: the portal grid layout puts the Docket Number in cell index 2 (a leading actions/expand column occupies earlier cells). The row selector (table tbody tr) and the docket-sheet anchor selector (a[href*='CpDocketSheet']) were correct and unchanged.
- Commands:
  - `PYTHONPATH=. .venv/bin/python probe_grid.py`: Read-only, name-free grid probe on the first window (2023-01-02 to 2023-01-06). Result: 1 table, 469 tbody tr rows all 19 cells wide; docket-pattern matched in cell index 2 for 108 of 469 rows (0 in cell 0); every matched row carried 2 CpDocketSheet anchors. Probe was deleted after use, never staged.
- Deviations: none. The probe script was a throwaway created at the repo root and deleted; it was never committed.
- Owner items: none
- Next agent:
  - The two live-run corrections are in place but not yet verified against the portal end to end. The owner runs the first live directed validation (for example PYTHONPATH=. .venv/bin/python scripts/collect.py --limit 5) to confirm CP-51-CR rows are now harvested and saved. Remember the portal grid puts the docket number in cell index 2.
## 2026-07-05: Phase 2, throttle-aware abort guard
- Outcome: done
- Built:
  - src/acquire/guard.py (new; portal-free AbortGuard tracking consecutive error and no-pdf streaks, thresholds ERROR_STREAK_ABORT=5 and NO_PDF_STREAK_ABORT=8)
  - scripts/collect.py (import AbortGuard; drop local ERROR_STREAK_ABORT; add screenshot() helper; instantiate one guard above the week loop so streaks persist across weeks; route error/no_pdf/saved outcomes through guard.record; abort and screenshot on a no-pdf streak)
  - src/config.py (MIN_DELAY 3->6, MAX_DELAY 7->12)
  - tests/test_abort_guard.py (new; 6 offline unit tests for the streak logic)
- Root cause: the abort guard counted only thrown exceptions, but soft rate-limiting arrives as a clean non-PDF HTTP response (429 or a slow-down page) that pdf_from_href reports as None. The no-pdf branch reset the streak and continued, so the guard never fired and the run would grind its whole budget against a throttling portal.
- Fix reasoning: a separate no-pdf streak aborts at 8, above the exception threshold of 5 because no-pdf is a softer, more ambiguous signal than a thrown exception; only a clean save resets the streaks, so an isolated genuine missing sheet cannot reach 8 while an unbroken throttle run does. Base delay doubled to avg ~9s (band 6-12) to back off below the cadence that provoked pushback at ~44 fetches, band widened proportionally to keep the rhythm randomized.
- Commands:
  - `PYTHONPATH=. .venv/bin/pytest -q`: full suite green offline, 29 passed (6 new).
  - `PYTHONPATH=. .venv/bin/python -c "import scripts.collect"`: import ok, no browser launched.
- Deviations: added src/acquire/guard.py, a file beyond the two named in the original diff request, so the streak logic imports and unit-tests without pulling in Playwright or contacting the portal; approved by the owner. AbortGuard() moved above the week loop per owner direction so the no-pdf and error streaks persist across week boundaries, since throttling spans weeks.
- Owner items: none. Fix is offline-verified only; the owner runs the first live directed validation to confirm the guard aborts and screenshots under real throttling.
- Next agent:
  - The no-pdf abort marks the in-flight week partial, so it is re-searched with fresh links next run; no fetched data is lost. Delay defaults are now 6/12 and overridable via MIN_DELAY/MAX_DELAY in .env.

## 2026-07-05: Exploration script
- Outcome: done
- Built:
  - scripts/explore.py (new; read-only corpus explorer, prints five labeled sections, stdlib only, no new dependency)
- Schema the queries bind to (read from the live database, not assumed):
  - judges: label column name_normalized, key id.
  - charge_categories: label column is name (not slug), key id.
  - charges: category_id to charge_categories.id, docket_number to cases.docket_number, plus disposition_category.
  - cases: judge_id to judges.id (the judge dimension for both judge coverage and the thin-cell view).
  - harvest_windows: status, total_rows, cp_criminal_rows, week_start (progress meter source).
- Design notes:
  - Opens the database read-only via sqlite3 URI mode=ro, so no write can occur and a missing file fails cleanly instead of creating an empty database. SELECT only, no init_db, no schema change.
  - Thin-cell threshold is the module constant MIN_CELL (default 5), overridable with the optional --min-cell flag.
  - Privacy: defendants is never joined or read; no defendant id or caption is selected or printed. Only counts, judge names (public officials), category and statute and disposition labels, and dates appear.
  - Each section prints "no rows yet" when empty, so an early-corpus run reads cleanly.
  - The run is guarded behind if __name__ == '__main__', so import has no side effect.

## 2026-07-05: Sentence-length exploration views
- Outcome: done
- Built:
  - scripts/explore.py (extended; added print_four_column helper and two new sections, sentence length by category and sentence length by judge, wired into main after the disposition section; docstring section list updated)
- Sentence schema the queries bind to (read from the live database, not assumed):
  - sentences: key id, charge_id to charges.id, sentence_type (VARCHAR), min_days (INTEGER), max_days (INTEGER), plus program, sentence_date, raw_text.
  - Lengths are already stored in days. min_days and max_days hold day counts (the parser applied the day=1, month=30, year=360 convention at parse time, so raw "11.00 Months 15.00 Days" is stored as 345). No conversion is applied in the explorer; the averages are taken directly over min_days and max_days.
  - Confinement type: sentence_type values present are Confinement (334), Probation (439), No Further Penalty (94), ARD (25), Fines and Costs (5). The length views filter to sentence_type = 'Confinement' so probation-only and fine-only dispositions do not dilute the figures.
  - The schema stores a min and a max, so both averages are reported (avg min days, avg max days) rather than collapsed to one.
- Design notes:
  - min_days IS NOT NULL is required so the shown count matches the rows feeding the averages. 16 confinement rows carry no parsed length; excluding them leaves 318 confinement sentences with a length.
  - Judge keying distinction, explicit for phase 5: the sentence-length-by-judge view keys on charges.disposition_judge_id (the sentencing judge, the official who imposed the sentence on that charge). The existing judge-coverage and thin-cell sections key on cases.judge_id (the assigned judge). Both linkages have full coverage over confinement sentences (334 of 334) so neither loses rows, but they answer different questions and must not be conflated.
  - Averages are rounded to whole days (SQL round, cast to int for display).
  - The by-judge view applies the same MIN_CELL threshold (default 5, overridable via --min-cell) as the thin-cell section; the by-category view is unthresholded, matching category depth.
  - Still read-only (mode=ro, SELECT only), defendants never joined or read, no defendant id or caption selected or printed, import has no side effect.
- Commands (offline, no portal contact):
  - `.venv/bin/python -m pytest tests/ -q`: existing suite green, 29 passed.
  - `PYTHONPATH=. .venv/bin/python scripts/explore.py`: all five prior sections plus the two new sentence-length sections printed, lengths in days, labels resolved, no traceback, no defendant name or caption.
  - `PYTHONPATH=. .venv/bin/python -c "import scripts.explore; print('import ok')"`: import ok, no side effect.
- Deviations: none.
- Owner items: none.
- Next agent:
  - Sentence lengths live in sentences.min_days and sentences.max_days, already in days (day=1, month=30, year=360), no conversion needed. Confinement is sentence_type = 'Confinement'. For a sentencing-judge cut use charges.disposition_judge_id; for the assigned judge use cases.judge_id.
  - Data-quality note visible in the run: one malformed judges row ("Confinement Min of 90.00 Days") appears in the judge-coverage section (keyed on cases.judge_id) but not in the sentence-length-by-judge section, so the sentencing-judge join is clean. A future cleanup task may want to scrub that stray judges row.
- Commands:
  - `sqlite3 data/processed/phl.db ".schema judges|charges|cases|charge_categories|harvest_windows"`: read the live schema; confirmed name_normalized, category_id, docket_number, judge_id, and that the category label column is name.
  - `.venv/bin/python -m pytest tests/ -q`: suite green, 29 passed (no tests added).
  - `PYTHONPATH=. .venv/bin/python scripts/explore.py`: all five sections printed against the live corpus (319 cases, 773 charges, 40 judges, 4 of 5 weeks complete, 705 CP-51-CR rows seen); categories and judges shown as resolved labels, not ids; no defendant name or caption in the output.
  - `PYTHONPATH=. .venv/bin/python -c "import scripts.explore; print('import ok')"`: import ok, no database write, no side effect.
- Deviations: none.
- Owner items:
  - Data-quality note (surfaced by the explorer, not caused by it): the judges table holds one junk row, "Confinement Min of 90.00 Days" (1 case), a parser artifact from an earlier phase. Fixing it belongs to a parser or loader task, not this read-only script.
- Next agent:
  - scripts/explore.py is strictly read-only and safe to run at any corpus size. Run it as PYTHONPATH=. .venv/bin/python scripts/explore.py (optionally --min-cell N) to watch the corpus grow. It writes nothing and contacts no portal.

## 2026-07-05: Static data dashboard
- Outcome: done
- Built:
  - scripts/dashboard.py (new; read-only script, writes one self-contained data/interim/dashboard.html, nine panels, matplotlib figures embedded as base64 PNG, run guarded behind if __name__ == '__main__')
  - src/analysis/corpus_queries.py (new; shared read-only query module, SELECT only over a mode=ro connection, returns plain row lists, single source of truth for the dashboard numbers)
  - requirements.txt (added matplotlib>=3.8, the plotting dependency this build requires)
- Plotting approach: matplotlib (newly added dependency), Agg backend, each figure serialized to a base64 PNG data URI and embedded as an inline <img>. The output HTML references no external URL (no CDN, no external script, no external font), so it opens with no internet connection. Inline CSS only.
- The nine panels:
  1. Collection progress: weeks complete out of 183 (progress-meter bar), CP-51-CR rows seen, corpus totals (cases, charges, sentences, judges).
  2. Category distribution: charges per category, descending bar plus table.
  3. Disposition breakdown: disposition_category shares including the null bucket (labeled open charges).
  4. Outcome mix per charge category: stacked share bar per category across the five sentence types plus a non-sentence bucket (charges with no sentence row), with an underlying counts table.
  5. Sentence length by type: Confinement and Probation only, avg min and max days by category with n, grouped bar; panel notes ARD, No Further Penalty, and Fines and Costs carry no length.
  6. Sentence length by judge: confinement avg min and max days by sentencing judge (charges.disposition_judge_id), cells at or above the threshold, with n.
  7. Judge coverage: cases per assigned judge (cases.judge_id), descending bar plus table.
  8. Thin-cell judge-signal readiness: category by assigned judge counts at or above the threshold, with a cell count.
  9. Time to disposition: avg filing-to-disposition days by category and by sentencing judge (cells at or above the threshold), each with n and a survivorship-bias caption.
- Schema columns bound (read from the live database, not assumed):
  - cases: judge_id (assigned judge), docket_number, filed_date. defendants never joined or read; defendant_id never selected.
  - charges: category_id to charge_categories.id, docket_number to cases.docket_number, disposition_category, disposition_date, disposition_judge_id (sentencing judge).
  - sentences: charge_id to charges.id, sentence_type, min_days, max_days (already in days, no conversion).
  - charge_categories: label column name, key id. judges: name_normalized, key id. harvest_windows: status, cp_criminal_rows.
- Small-sample honesty and guards: every panel that shows an average shows its n beside it (panels 5, 6, 9); shares in panels 3 and 4 carry the underlying counts; any empty result renders a "no data yet" note instead of a broken chart. Header shows the generation timestamp and current corpus totals, so a saved file is self-dating.
- Commands (offline, no portal contact):
  - `.venv/bin/pip install matplotlib`: installed matplotlib 3.11.0 into the venv.
  - `.venv/bin/python -m pytest tests/ -q`: suite green, 29 passed (no tests added).
  - `PYTHONPATH=. .venv/bin/python scripts/dashboard.py`: wrote data/interim/dashboard.html (330K), no traceback, all nine panel headings present.
  - `PYTHONPATH=. .venv/bin/python -c "import scripts.dashboard; print('import ok')"`: import ok, no side effect (run guarded behind __main__).
  - Output audit greps: zero http(s) URLs, all six img src attributes are data: URIs, no <link>/<script>/@import/googleapis/fonts. tokens; the only "defendant" is the header phrase "no defendant data", the "caption" hits are the CSS class, the "cdn" hits are random substrings inside base64 blobs. No defendant name, no defendant id, no case caption in the file.
- Deviations:
  - Per owner direction, scripts/explore.py was left exactly as committed and is not staged. The shared queries were built fresh in src/analysis/corpus_queries.py; explore.py was not refactored to consume it. This leaves mild, accepted duplication between the two files (both hold the corpus-totals, category, disposition, thin-cell, judge-coverage, and confinement-length queries). A shared-query refactor of explore.py, if wanted, is a separate task.
  - Sentence length by type (panel 5) covers both Confinement and Probation, extending explore.py's confinement-only length view, because the task panel asks for both types that carry a length.
  - Time to disposition by judge keys on the sentencing judge (charges.disposition_judge_id), labeled as such, matching panel 6; the by-category cut uses cases.filed_date and charges.disposition_date. Both are raw survivorship-biased averages, captioned on the panel.
- Owner items:
  - Review and commit. Staged for review: scripts/dashboard.py, src/analysis/corpus_queries.py, requirements.txt, tasks/worklog.md. Not committed or pushed.
  - data/interim/dashboard.html is gitignored (.gitignore has data/interim/) and is not staged.
- Next agent:
  - The dashboard is read-only. Regenerate on demand with PYTHONPATH=. .venv/bin/python scripts/dashboard.py (optional --min-cell N). Output at data/interim/dashboard.html, self-contained, no external URL.
  - Corpus at build time: 723 cases, 1656 charges, judges and sentences per the header. Numbers come from src/analysis/corpus_queries.py; that module is the single source of truth for the panels.

## 2026-07-05: Charge categorization: eliminate other
- Outcome: done
- Built:
  - data/lookups/charge_categories.yaml: 12 new categories (possessing-instrument-of-crime, reckless-endangerment, criminal-mischief, endangering-welfare-children, strangulation, unlawful-restraint, resisting-fleeing, arson, communication-facility, public-order, other-traffic, inchoate); ~60 new prefix keys covering 100 percent of the prior other set; new inchoate block (prefixes 18 § 901/902/903, ordered contains-rules, fallback inchoate).
  - src/db/load.py: added resolve_inchoate and categorize_charge (inchoate resolves by offense text after the " - " separator, specific-before-general, bare falls to inchoate); load_lookups now returns the inchoate block; loader calls categorize_charge. categorize_statute unchanged.
  - src/parse/docket_parser.py: two parse-level fixes. (1) Drop a leading "IC" (Indirect Criminal contempt) marker token before statute detection, so those rows parse a real statute instead of null. (2) Skip continuation lines containing "Unknown Statute" so a void placeholder charge never pollutes the prior charge's offense.
  - scripts/recategorize.py (new): in-place, idempotent recategorize. Recomputes each charge's category from its stored statute and offense, updates only charges.category_id, reuses the same YAML and mapper. Reads only statute, offense, category.
  - tests/test_load_helpers.py: added five tests loading the shipped YAML: new dedicated categories, remaps into existing, inchoate named-target, bare-inchoate, and specific-before-general ordering (conspiracy retail theft to retail-theft not theft; conspiracy aggravated assault to aggravated-assault not simple-assault).
- Scope note: the task assumed open-case charges carry category_id null; in the live DB category_id was never null (the loader assigns a category, defaulting to other, to every charge). Per owner amendment, retired that constraint and recategorized status-agnostically; outcome exclusion runs on disposition_category, which stays null on open cases, so assigning a type category to open charges is harmless.
- Parser artifact set (condition 1, proven read-only before any reparse): exactly 6 charges across exactly 6 dockets. 5 null-statute IC-contempt rows (CP-51-CR-0000116/0000284/0000583/0001122-2023, CP-51-CR-0004851-2025) and 1 concatenated filler row (CP-51-CR-0000234-2023 seq 3). No others surfaced.
- Commands:
  - condition-1 artifact query: 5 null-statute charges + 1 "Unknown Statute" filler = 6 charges in 6 distinct dockets. Matched the plan; continued.
  - targeted reparse+reload of the 6 dockets (scratchpad one-off, via parse_docket + assert_no_leak + load_record): total charges stayed 1656; pre/post diff moved exactly the 6 expected rows (5 statutes null to 23 § 6114 §§ A, 1 offense cleaned to "Careless Driving"), nothing else. Remaining null/blank statutes 0, remaining "Unknown Statute" fillers 0, remaining leading "IC " offenses 0.
  - privacy on reparse (condition 6): each of the 6 regenerated interim JSON files is hash-only (64-hex defendant_hash), keys limited to the contract, no defendant_name/caption/" v. "/birth/dob substring.
  - `PYTHONPATH=. python3 scripts/recategorize.py` (run 1): 1656 charges, 557 reassigned; distribution matches the amended expected table; other = 0.
  - idempotency (condition 4): run 2 reassigned 0; per-slug counts identical to run 1 (diff empty); charge_categories holds 28 rows for 28 distinct slugs (16 original + 12 new, no duplication).
  - task verification queries: full distribution as below; `SELECT COUNT(*) ... WHERE cc.slug='other'` returned 0; total charges 1656.
  - `python3 -m pytest -q`: 34 passed (was 29; 5 categorization tests added).
- Final distribution (other = 0): Firearms 349, Theft 177, Drug Delivery 162, Possessing Instrument of Crime 111, Simple Assault 109, Aggravated Assault 107, Homicide 82, Recklessly Endangering (REAP) 72, Robbery 67, Drug Possession 67, Sexual Offenses 54, Burglary 38, Fraud and Forgery 37, Criminal Trespass 36, Public Order 29, Inchoate Offenses 28, Terroristic Threats 24, Criminal Mischief 21, Resisting / Fleeing 18, Retail Theft 14, Endangering Welfare of Children 11, Unlawful Restraint / Kidnapping 10, Strangulation 10, DUI 10, Other Traffic 7, Criminal Use of Communication Facility 4, Arson 2. Total 1656.
- Deviations from the frozen task file (all per owner amendment): 18 § 7512 got its own communication-facility category rather than folding into fraud-forgery, so 12 new seed rows not 11, and fraud-forgery lands at 37 not 41; the null-category open-case constraint was retired as described above. 18 § 3928 to theft and 18 § 3301 to a dedicated arson category were confirmed as planned.
- Owner items:
  - Review and commit. Staged for review: data/lookups/charge_categories.yaml, src/db/load.py, src/parse/docket_parser.py, scripts/recategorize.py, tests/test_load_helpers.py, tasks/worklog.md. Regenerated interim JSON (6 dockets) and data/processed/phl.db are gitignored (data/interim/, data/processed/) and not staged.
- Next agent:
  - Recategorize is in-place and idempotent: rerun any time with `PYTHONPATH=. python3 scripts/recategorize.py`. It reads stored statute+offense only; no reparse or re-collection.
  - Future full loads categorize correctly on their own (loader uses categorize_charge), including inchoate resolution and the two parser fixes, so freshly parsed dockets will not reintroduce other for these statutes.
  - The inchoate resolver keys on the offense text after " - "; if new target crimes appear that are not in the ordered contains-rules, they fall to the inchoate bucket by design. Extend the rules block in charge_categories.yaml to reclassify them.

## 2026-07-06: Docs: Municipal Court expansion recorded, D-18 and D-19
- Outcome: done
- Built:
  - docs/DECISIONS.md: added D-18 (MC expansion scope and rules) and D-19 (window amendment, published data 2025 forward), inserted after D-17 and before the Open section.
  - docs/METHODOLOGY.md: replaced the single "Municipal Court is out of scope" bullet with five two-court rule bullets (two courts never blended, the CP selection effect, MC exclusions, de novo appeals, consolidated siblings).
  - docs/ROADMAP.md: bumped Last updated to 2026-07-06; added Phases-table row "7 | Municipal Court expansion | next (runs before Phase 5)"; removed the parked "Municipal Court coverage" bullet; inserted the Phase 7 block (five stages plus acceptance) before the Parked section.
  - docs/DATA_SOURCE.md: added a "Municipal Court sheets (MC-51-CR)" section between the anatomy list and Parser field mapping, recording the recon findings.
  - docs/DATABASE.md: changed cases.court_type note to "Common Pleas or Municipal Court (D-18)"; added a dc_number row directly under otn.
  - tasks/worklog.md: this entry.
- Commands:
  - `git diff` review of the six files, then a single commit "Docs: record MC expansion, D-18 and D-19, Phase 7" (owner-approved, once per task).
- Deviations: none. All six anchors matched the files exactly; no improvisation. Two judgment calls were owner-confirmed before editing: the Phases-table row wording and the Last-updated date bump.
- Owner items: none outstanding beyond the approved commit.
- Next agent: Phase 7 (Municipal Court expansion) is the next phase to start, before Phase 5, per D-18, D-19, and the new ROADMAP Phase 7 block. The recon that backs these docs was read-only; the three renderings flagged unverified (plea versus trial labeling, sentence and AMP rendering, held-for-court) gate MC collection and must be proven on MC fixtures first.

## 2026-07-06: Phase 7 stages 1 and 2: MC parser delta and fixture gate
- Outcome: done
- Built:
  - src/parse/docket_parser.py: (a) split parse_docket into parse_docket (opens PDF) plus parse_docket_text (text to record), a behavior-neutral refactor so the section logic is testable on synthetic text; (b) detect_court_type from the docket prefix (MC- to Municipal Court, else Common Pleas) and skip the MUNICIPAL COURT banner on every page; (c) registered RELATED CASES, CASE PARTICIPANTS, BAIL INFORMATION, CASE FINANCIAL INFORMATION as known sections, extended the transient name and DOB lookup to also scan CASE PARTICIPANTS so the defendant hash basis is unchanged now that CASE PARTICIPANTS is its own section; (d) parse_related_cases into docket number, court, association reason using a controlled reason vocabulary only, never free text; (e) extract dc_number from the District Control Number line. Record gains case.court_type (now prefix-derived), case.dc_number, and top-level related_cases.
  - src/identity.py: assert_related_cases_clean, the structural half of the privacy assertion; fails the write if any related-cases entry carries a field beyond docket_number, court, association_reason.
  - scripts/parse_fixtures.py: calls assert_related_cases_clean after assert_no_leak.
  - scripts/fetch_mc_fixtures.py: throwaway MC fixture fetcher, reuses portal.pdf_from_href, AbortGuard, and the collector Date Filed search; harvests only the docket cell and sheet anchor for MC-51-CR rows, never the caption column; --dry-run reports the anchor before any fetch; hard cap 20. NOT staged.
  - tests/test_mc_parser.py: 7 unit tests on synthetic text (court type both prefixes, dc_number, related-cases caption dropped, header and free-text ignored, privacy guard raises on extra key, CP shape intact).
  - tasks/auditpack-p7.md: owner hand-check pack for the three gate renderings, name-free.
- Commands:
  - pytest tests/test_mc_parser.py: 7 passed.
  - CP regression diff (scratchpad harness, in-memory, no interim overwrite): 1258 CP baselines diffed, 1258 identical on existing fields, 0 mismatched, 0 parse failures. Only additions are case.dc_number (populated) and related_cases (empty on CP). Strict superset of the 31-fixture set (the ledger fixture tag was gone after the collector rebuild, so all CP interim on disk was diffed).
  - fetch_mc_fixtures.py --dry-run (owner-approved, portal): week 2025-01-06 to 01-10, 1002 result rows, 133 MC-51-CR rows, sheet anchor CpDocketSheet (same endpoint as CP, so the proven fetch path applies).
  - fetch_mc_fixtures.py (owner-approved, portal): 20 MC fixtures saved, no throttling.
  - fetch_mc_fixtures.py --start 2025-01-13 --end 2025-01-17 (owner-approved additional week, portal): 1012 rows, 158 MC-51-CR, 20 more MC fixtures saved, no throttling.
  - MC parse (scratchpad, MC-only), full fetched set: 40 of 40 parsed ok, 0 privacy failures, dc_number present on all 40.
- Fixture set (selected 10 of 20 fetched, filings 2025, one-word reason):
  - MC-51-CR-0000612-2025 plea (also the sentenced case, Probation 12 months)
  - MC-51-CR-0000580-2025 amp (ARD diversion; AMP-specific not found this week)
  - MC-51-CR-0000577-2025 held
  - MC-51-CR-0000586-2025 held
  - MC-51-CR-0000599-2025 held
  - MC-51-CR-0000609-2025 held
  - MC-51-CR-0000608-2025 extra (Withdrawn disposition variant)
  - MC-51-CR-0000591-2025 open (Inactive, reciprocal sibling group)
  - MC-51-CR-0000592-2025 open (Inactive, reciprocal sibling group)
  - MC-51-CR-0000593-2025 extra (reciprocal sibling)
  - MC-51-CR-0001081-2025 amp (second ARD diversion, week 2; 12 months plus a 60 day license suspension)
  - MC-51-CR-0001056-2025 trial (week 2; a Waiver Trial is listed but the case is Active with no verdict entered)
  - Trial verdict: not found across two sampled weeks (filed 2025-01-06 and 2025-01-13). A Waiver Trial appears listed on the Active case 0001056 with no verdict entered; no decided Guilty or Not Guilty verdict was found. AMP-specific diversion was also not found in either week; ARD diversion covers the diversion rendering.
- Gate results: plea labeled "Guilty Plea - Negotiated"; diversion "ARD - County" with an ARD 12-month component; held for court renders as a per-charge "Held for Court" disposition with no date and no sentence (non-terminal, D-18); dc_number populated on every fixture; related_cases parsed with reciprocal siblings visible (0591 and 0592 reference each other) and Consolidated versus Joined groupings captured. Zero captions, names, or DOBs in any output.
- Regression proof: scripted field-level diff, 1258 of 1258 CP records value-identical on all pre-existing fields, the only differences the two new keys. Not eyeballed.
- Deviations:
  - dc_number is populated (not null) on the CP corpus because CP sheets print a District Control Number in the same Case Local Number(s) table. Owner approved populating on both courts and amending the Step 5 expectation.
  - parse_docket_text refactor added beyond the four bounded changes, accepted by the owner as behavior-neutral and proven by the regression diff.
  - The 31-fixture ledger tag no longer exists after the collector rebuild; the regression was run over all 1258 CP interim records instead, a strict superset.
  - CASE PARTICIPANTS name and DOB lookup extension (deviation). The transient defendant name and DOB lookup was extended to scan CASE PARTICIPANTS in addition to DEFENDANT INFORMATION. Reason: MC sheets carry the defendant name under CASE PARTICIPANTS, not under DEFENDANT INFORMATION; and on CP sheets the "Defendant" name line sat under a CASE PARTICIPANTS subheader that used to fold into DEFENDANT INFORMATION until this task registered CASE PARTICIPANTS as its own section. Scanning both keeps the first-match, and thus the defendant hash basis, unchanged (confirmed by the regression: defendant_hash identical on all 1258 CP records).
- Owner items:
  - Ledger rows were written for 40 MC fixtures across two weeks (RawDocket, note "mc fixture" then parse_status parsed); a db-snapshot re-upload at close was flagged as the trigger for this.
  - Audit pack tasks/auditpack-p7.md awaits owner pass on the three renderings.
  - One additional filing week (filed 2025-01-13 to 01-17) was fetched at owner approval; AMP-specific and a decided trial verdict were still not found. Further weeks are optional and may hit diminishing returns; both renderings appear rare in the early-2025 MC-51-CR population.
  - assert_no_leak guards only the defendant name and DOB, not other third-party names (for example a "Probation Officer LastName, FirstName" line); none leaked here, flagged for stage 3.
- Post-review clarifications (owner review items):
  1. min_days rule, not bug. min_days on MC-51-CR-0000612-2025 is 360 because the sheet prints Probation "Max of 12.00 Months" only and save_current_sentence sets min_days = max_days when just a Max is present (an existing CP-validated fallback applied identically to every CP record). Documented, not changed. Caveat: for a probation term with no printed minimum this reports a minimum equal to the maximum; changing it would alter CP output and is out of scope for this task.
  2. disposition_date null rule, not bug. The held charges on MC-51-CR-0000577-2025 carry disposition_date null even though the event header prints "Preliminary Hearing 05/19/2025 Final Disposition". disposition_date is sourced only from the per-charge sentencing/judge line; held-for-court charges have no such line, so the field is null. Capturing the event-header date for non-terminal held events is deferred to stage 3 (the held date is distinct from a sentencing date; D-18 treats held-for-court as non-terminal).
  3. related_cases association_reason stores the grouping header, not the Association Reason column. The value captured (for example "Consolidated Defendant Cases", "Joined Codefendant Cases", or "Related") is the controlled grouping heading that precedes the docket rows, not the sheet's rightmost Association Reason column cell. That column sits immediately to the right of the Related Case Caption column, so reading it positionally risks capturing caption text; the grouping heading is captured instead as a caption-safe proxy from a fixed vocabulary. Audit pack wording corrected to match.
  4. Held-for-court CP linkage IS on the MC sheet. Correcting the audit pack: the CP docket a held MC case is bound for prints in CASE INFORMATION as "Cross Court Docket Nos" (confirmed CP-51-CR values on the held fixtures 0000577, 0000586, 0000609). It is not captured in this task; recorded as a stage 3 item. It is not in RELATED CASES.
- Next agent: stage 3 is schema and loader (cases.dc_number, court_type loading, OTN plus DCN sibling grouping, the de novo supersession rule). Interim JSON for MC is on disk (gitignored). Stage 3 items surfaced here: capture the Cross Court Docket Nos value from CASE INFORMATION (the held-to CP docket); decide whether non-terminal held events should carry the event-header date as disposition_date; and revisit whether the per-row Association Reason column can be read caption-safely. Related-cases reason vocabulary is controlled and may need extending if new phrases appear; extend ASSOCIATION_REASONS in docket_parser.py.
