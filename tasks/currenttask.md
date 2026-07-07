# Task: Phase 7, stages 1 and 2. MC parser delta and the MC fixture gate

## Orientation

CP51 parses Philadelphia criminal docket sheet PDFs into SQLite. Phases 1, 3,
4 are complete; the CP parser is validated against a 31-docket fixture set.
Phase 7 (DECISIONS.md D-18, D-19; ROADMAP.md Phase 7 block) extends the
system to Municipal Court, MC-51-CR series only. This task is stages 1 and 2
of that block: the parser delta that lets the existing parser read MC sheets,
proven by a hand-picked MC fixture set that must cover the three renderings
recon could not verify. Stages 3 to 5 (loader and schema, collector, stats
filter) are later tasks. Do not touch them.

Recon findings on MC sheets are recorded in docs/DATA_SOURCE.md, section
"Municipal Court sheets (MC-51-CR)". Read it before planning. The scope rules
are DECISIONS.md D-18 and D-19. Read both.

## Ground rules

1. Post an implementation plan and wait for approval before running anything.
   The plan must include the inspect-and-report items in Step 1.
2. Every command is ask-first. Commit and push are owner-only; you stage and
   stop.
3. Maintain a task artifact as you work. Write the tasks/worklog.md entry
   before the final commit so the commit contains it (D-17).
4. This file is frozen. Corrections arrive as one-line diffs from the owner.
5. Privacy, absolute: defendant names and dates of birth exist in memory only.
   New in this task: the RELATED CASES section on MC sheets carries a caption
   column with third-party names. Parse that section for docket number, court,
   and association reason only. No caption text may ever be stored, printed,
   logged, committed, or written to the worklog. The search results page also
   has a Case Caption column: never read it; harvest Docket Number and the
   docket-sheet link only.
6. No em dashes in any code, comment, commit message, or worklog text.
7. Portal contact is owner-directed only (D-15). Randomized politeness delays
   on every fetch. Never refetch a cached docket.
8. Do not modify the database schema in this task. cases.dc_number and all
   loading changes are stage 3. This task ends at parsed interim output.

## Step 0: repo state check

`[agent] [once per task, ask first]` `git log --oneline -5` and `git status`.
Report both. Working tree must be clean before any edit.

## Step 1: inspect and report (goes in your implementation plan)

The planner does not have the parser source. Before proposing edits, read the
repo and report in your plan:

1. How src/parse/docket_parser.py recognizes and registers sections: the
   exact mechanism (header list, regex table, state machine), with the code
   location, and what currently happens to an unrecognized section header
   (which section its lines fold into).
2. How the court banner line is handled today, and where court type could be
   detected (banner text, docket number prefix, or both). Propose one.
3. Where the Case Local Number(s) table appears in the text extraction and
   what its rows look like, so the District Control Number extraction rule
   can be exact.
4. Whether the four MC recon sheets are already in the local PDF cache, with
   their paths, or must be refetched.
5. How the CP fixture set is fetched and cached (scripts/fetch_fixtures.py
   behavior, cache directory, raw_dockets ledger interaction), and whether it
   can fetch an MC-51-CR docket number unchanged.
6. The parser's existing privacy assertion on write: where it lives and what
   it checks, so the related-cases caption guard can extend the same
   mechanism.
7. The exact shape of one CP interim JSON record (top-level keys only), so
   the regression rule in Step 5 is checkable.

Your plan then lays out the concrete edits for Steps 2 to 6 against those
facts. Approval of the plan is the gate; nothing runs before it.

## Step 2: MC fixture acquisition (portal, every run owner-approved)

Goal: a cached MC fixture set of at least 8 and at most 15 MC-51-CR dockets,
filings 2025 forward (D-19), that includes at minimum:

- one case closed by conviction via guilty plea and, if findable, one closed
  by trial verdict (proves plea versus trial disposition labeling),
- one sentenced case or one AMP-diverted case, ideally one of each (proves
  sentence and diversion rendering),
- one held-for-court case (proves how the CP docket surfaces),
- one still-open case (proves pending handling on MC).

Method, subject to your plan: one Date Filed search on an early 2025 week
(early in the year so cases have had time to close), harvest MC-51-CR docket
numbers only (regex on the Docket Number cell; never the caption column;
MC-51-SU, MC-51-MD, traffic, and every CP row are skipped), fetch a batch of
sheets within a hard budget you state in the plan (suggested: 20 fetches per
run), inspect statuses locally, and select the fixture set. If a required
rendering is missing, propose one additional week and ask before fetching.
Reuse the proven fetch path; do not write a new portal module. AbortGuard
discipline from the CP collector applies if you touch the results page.

Report the selected fixture list as docket numbers with a one-word reason
each (plea, trial, sentenced, amp, held, open, extra). No captions, no names.

## Step 3: parser delta

Bounded delta, no separate MC parse path (ROADMAP Phase 7 stage 1):

1. Accept the MUNICIPAL COURT OF PHILADELPHIA COUNTY banner wherever the CP
   banner is handled today; set court type in the parsed record: value
   "Municipal Court" for MC-51 dockets, "Common Pleas" for CP-51, using the
   detection you proposed in Step 1 item 2.
2. Register RELATED CASES, CASE PARTICIPANTS, BAIL INFORMATION, and CASE
   FINANCIAL INFORMATION as known sections so their lines stop folding into
   CASE INFORMATION. CASE PARTICIPANTS, BAIL INFORMATION, and CASE FINANCIAL
   INFORMATION are recognized and skipped, not parsed.
3. Parse RELATED CASES into a list on the record: docket number, court, and
   association reason per row. The caption column is never captured; extend
   the existing privacy assertion so a write fails if a related-cases entry
   carries any field beyond those three.
4. Extract the District Control Number from the Case Local Number(s) table
   into a dc_number field on the parsed record (string, as printed, null when
   absent). Parser output only; no schema or loader change.
5. Tests: unit tests on synthetic text fixtures for the section registration
   (a RELATED CASES block with a fake caption must produce entries without
   it), the dc_number extraction, court type detection for both prefixes, and
   one regression test asserting a CP-shaped input still parses identically.
   Synthetic fixtures use fictional names in the style already used by the
   repo (surname Example) and docket MC-51-CR-0000000-2025.

## Step 4: parse the MC fixtures, prove the gate

`[agent] [once per task, ask first]` run the parser over the MC fixture set.
Expected: every fixture parses with parse_status ok, zero privacy assertion
failures. Then verify and report, quoting field values (dispositions,
sentence components, statuses; never names):

1. Plea versus trial labeling on the conviction fixtures: the disposition
   strings as parsed, and that they are distinguishable as plea versus
   verdict.
2. Sentence or AMP rendering on the sentenced or diverted fixture: sentence
   components as parsed (type, lengths, raw text), or the diversion
   disposition string.
3. Held-for-court rendering: the case status and per-charge disposition
   strings as parsed, and whether the sheet names the CP docket it was held
   to (if it appears in RELATED CASES or elsewhere, say where).
4. dc_number present on every fixture that prints one.
5. related_cases parsed on any fixture that has the section, with reciprocal
   siblings visible where they exist.

## Step 5: CP regression proof

`[agent] [once per task, ask first]` re-run the parser over all 31 CP
fixtures. Expected, precomputed: 31 of 31 parse with parse_status ok; for
every record, all previously existing fields are value-identical to the
current interim JSON; the only permitted differences are the new keys (dc_number as printed, CP sheets carry a DCN too; related_cases empty). court_type already exists in the record and must be value-identical on all 31.
Prove it with a scripted field-level diff, not eyeballing. Any other
difference is a stop-and-report, not a fix.

## Step 6: audit pack for the owner

Write a small audit pack (markdown, gitignored location or tasks/ artifact,
your plan says which) containing, for each gate rendering, the docket number
and the parsed fields quoted next to the raw text lines they came from, so
the owner can hand-check the three renderings. No names, no captions, no
DOBs. The owner's pass on this pack is part of the gate.

## Step 7: worklog and staging

Write the tasks/worklog.md entry (title: "Phase 7 stages 1 and 2: MC parser
delta and fixture gate"): outcome, edits, fixture list with reasons, gate
results, regression proof summary, deviations, owner items, next-agent notes
(stage 3 is next: schema dc_number, court_type loading, sibling grouping, de
novo rule). Then stage for owner review: the parser, its tests, the worklog.
Interim JSON and PDF caches stay gitignored and unstaged. Stop; the owner
commits and pushes.

## Definition of done

- Implementation plan posted with all seven Step 1 items and approved before
  any execution.
- MC fixture set cached, 8 to 15 dockets, 2025 forward, covering plea
  conviction, sentenced or AMP, held-for-court, and open; trial verdict
  included if findable, absence reported if not.
- Parser delta implemented as four bounded changes; no other parse behavior
  altered; unit tests pass.
- All MC fixtures parse ok; the three gate renderings verified and reported
  with quoted field values; privacy assertion extended and holding.
- CP regression: 31 of 31 identical on existing fields, proven by scripted
  diff.
- Audit pack delivered; owner pass recorded.
- No caption text, defendant name, third-party name, or DOB anywhere: not in
  code, output, logs, worklog, or the audit pack.
- No schema change, no loader change, no collector change.
- Worklog entry present in the final commit; only parser, tests, and worklog
  staged.
- No em dashes introduced.