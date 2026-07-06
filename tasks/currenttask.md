# Task: Record the Municipal Court expansion (docs only)

## Orientation

CP51 is expanding from Common Pleas (CP-51-CR) to also cover Philadelphia
Municipal Court criminal cases (MC-51-CR). The owner has locked the scope
decisions and a read-only recon of four real MC docket sheets has established
the sheet anatomy. This task records all of it in the docs. Docs only: no
code, no schema migration, no collection. The MC implementation itself is
Phase 7, dispatched separately after this lands.

Each edit below gives an anchor (existing text) and the exact change. If any
anchor does not match the file as it stands, stop and report the mismatch
instead of improvising. No em dashes anywhere. Synthetic examples only.

## Edit 1: DECISIONS.md, two new decisions

Append after D-17, before the `## Open` section:

```
**D-18 Municipal Court expansion; scope and rules (2026-07-06).** CP51 covers
both Philadelphia criminal trial courts. In scope: the MC-51-CR docket series
only. Out of scope: MC-51-SU (summaries), MC-51-MD (miscellaneous), the
traffic division, and any CP or MC series other than -CR. Held for Court and
Proceed to Court are non-terminal statuses, never counted as outcomes; the
outcome of a held felony is read from its CP docket. When an MC conviction is
appealed de novo to CP, the CP result is the outcome of record and the MC
result is superseded. Dockets sharing an OTN and District Control Number form
a consolidated sibling group (confirmed on real MC sheets via the RELATED
CASES section): siblings are kept as separate case rows with distinct charge
sets, never merged and never counted as independent incidents; incident-level
stats key on the OTN plus DCN group. Every output carries its source court;
courts are never silently blended. Comparable-tool precedent: D-13's
reference keeps its two court tiers separate and headlines the lower court.

**D-19 Window amendment: published data 2025 forward (2026-07-06).** Amends
D-16. The published dataset and all go-forward collection cover filings from
2025-01-01 for both courts. The 2023 and 2024 CP data already collected stays
on disk and in the database but is excluded from published stats by filter,
not deletion, so the window can extend backward later by config alone. Reason:
MC collection starts at 2025 and cross-court stats must draw from one window;
a two-window release would invite silent blending, which D-18 forbids.
```

## Edit 2: METHODOLOGY.md, replace the MC bullet with the two-court rules

Anchor (replace this bullet):

```
- **Municipal Court is out of scope.** Many Philadelphia cases begin and end
  in Municipal Court; CP51 covers Common Pleas only for now (ROADMAP).
```

Replacement:

```
- **Two courts, never blended (D-18).** Every metric is computed and shown
  per source court. Municipal Court headlines charges that lead as
  misdemeanors (DUI, standalone simple assault, retail theft, small drug
  possession); Common Pleas headlines felonies. A combined view, where shown,
  is labeled as combined.
- **The CP selection effect.** A misdemeanor appearing in a Common Pleas case
  is there because it was co-charged with a felony. CP-only numbers for such
  charges describe the felony-adjacent slice, not the standalone charge, and
  the product says so wherever they are shown.
- **MC exclusions.** MC-51-SU, MC-51-MD, and traffic-division matters are out
  of scope. Held for Court and Proceed to Court are non-terminal and never
  enter a denominator; a held felony's outcome is read from its CP docket.
- **De novo appeals.** When an MC conviction is retried de novo in CP, the CP
  result is the outcome of record; the superseded MC result never counts.
- **Consolidated siblings.** MC dockets sharing an OTN and District Control
  Number are one incident charged across sibling dockets. Charge-level stats
  may use each charge once; incident-level counts key on the OTN plus DCN
  group, so one incident is never counted as five.
```

## Edit 3: ROADMAP.md, unpark MC and add Phase 7

Remove this bullet from `## Parked (deliberately not now)`:

```
- **Municipal Court coverage.** Many Philadelphia cases live entirely in MC;
  large scope expansion, revisit after CP is solid.
```

Insert after the Phase 6 block, before the Parked section:

```
### Phase 7: Municipal Court expansion (scheduled next, before Phase 5)

Extends acquisition, parsing, and loading to the MC-51-CR docket series under
D-18 and D-19. Recon on real MC sheets confirmed the CP parser runs with a
small bounded delta; MC gets no separate parse path.

Stages:
1. Parser delta: skip the MUNICIPAL COURT OF PHILADELPHIA COUNTY banner;
   register RELATED CASES, CASE PARTICIPANTS, BAIL INFORMATION, and CASE
   FINANCIAL INFORMATION as sections so RELATED CASES third-party captions
   stop folding into CASE INFORMATION; extract District Control Number from
   the Case Local Number(s) table; parse RELATED CASES docket number, court,
   and association reason while never storing its caption column.
2. MC fixture validation, the gate: a hand-picked MC fixture set that must
   include at least one case closed by conviction (verifies plea versus trial
   labeling), one sentenced or AMP-diverted case (verifies the sentence and
   diversion rendering), and one held-for-court case (verifies how the CP
   docket surfaces). These three renderings are unverified by recon and block
   collection until proven.
3. Loader and schema: populate cases.court_type with Municipal Court, add
   cases.dc_number, implement the consolidated-sibling grouping and the de
   novo outcome-of-record rule.
4. Collector: harvest MC-51-CR rows from the same search results (same
   CpDocketSheet link pattern, confirmed by recon), same caption privacy
   rule, window per D-19.
5. Stats layer filter: published outputs restrict to filings 2025 forward for
   both courts.

Acceptance: MC fixtures parse with zero privacy sentinels and correct fields
for all three unverified renderings; a collection batch loads MC cases with
court_type, dc_number, and sibling groups populated; no SU, MD, or traffic
docket enters the database; the published-stats filter excludes pre-2025
filings; idempotency holds across a repeated run.
```

Also update the doc's status header if it summarizes phase order, so Phase 7
is shown as the next phase to start.

## Edit 4: DATA_SOURCE.md, MC sheet anatomy

Insert a new section after `## Anatomy of a docket sheet` content ends and
before `## Parser field mapping`:

```
## Municipal Court sheets (MC-51-CR)

Recon on four real 2026 MC sheets (two open, two closed) established:

- Banner reads MUNICIPAL COURT OF PHILADELPHIA COUNTY; everything else about
  the page furniture matches CP.
- Four sections CP sheets do not have: RELATED CASES (between CASE
  INFORMATION and STATUS INFORMATION), CASE PARTICIPANTS, BAIL INFORMATION,
  and CASE FINANCIAL INFORMATION (closed cases only).
- The charges grid is CP-identical: same columns, statute notation, grades,
  and continuation-line behavior. Ungraded rows (DUI, drug) leave the grade
  column blank.
- Judge Assigned is present but blank on all sampled sheets, open and closed.
  Judges appear by name only in CALENDAR EVENTS and ENTRIES. The disposition
  judge field is expected to populate on sentenced cases; unverified.
- OTN appears in CASE INFORMATION and on every charge row. The District
  Control Number lives inside the Case Local Number(s) table, not as a
  standalone field.
- RELATED CASES lists consolidated sibling dockets reciprocally, with an
  association reason. Its caption column contains third-party names and is
  never stored, printed, or logged; the section is parsed for docket number,
  court, and association reason only.
- Unverified pending MC fixtures: plea versus trial disposition labeling,
  sentence and AMP rendering, and held-for-court rendering.
```

## Edit 5: DATABASE.md, cases table notes

In the `### cases` table: change the `court_type` row description from
`default Common Pleas` to `Common Pleas or Municipal Court (D-18)`, and add a
row directly under `otn`:

```
| dc_number | str(40), null | District Control Number, from the Case Local Number(s) table; with otn, keys consolidated sibling groups (D-18). Added in Phase 7 |
```

## Edit 6: worklog entry

Write the `tasks/worklog.md` entry (title: "Docs: Municipal Court expansion
recorded, D-18 and D-19") before the final commit, summarizing the six edits.

## Commands

`[agent] [once per task, ask first]` `git diff` review of the six files, then
a single commit, message "Docs: record MC expansion, D-18 and D-19, Phase 7".

## Definition of done

- All six edits applied with anchors matched exactly (any mismatch reported,
  not improvised).
- No file outside DECISIONS.md, METHODOLOGY.md, ROADMAP.md, DATA_SOURCE.md,
  DATABASE.md, and tasks/worklog.md is touched.
- No em dashes introduced. No real defendant or third-party name anywhere.
- Worklog entry present in the final commit.