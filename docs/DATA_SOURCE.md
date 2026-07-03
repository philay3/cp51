# Data source

> Status: validated. The anatomy and quirks below were confirmed against the
> 31-docket phase 3 fixture set; items marked "confirmed" are observed fact,
> not expectation. Last updated 2026-07-02.

## Source

Pennsylvania UJS Web Portal: public Court of Common Pleas criminal docket
sheets and Court Summary reports, free to the public. Philadelphia Common
Pleas criminal dockets follow the format `CP-51-CR-{seven digit sequence}-{year}`,
where 51 is Philadelphia's county code. Cases are collectable two ways: drive
the portal's search form with filters (Common Pleas, county Philadelphia), or
enumerate sequence numbers per year. All examples in this documentation use
the synthetic docket `CP-51-CR-0000000-2024`; sequence 0000000 is never issued.

Why this source carries the whole project: Pennsylvania has no public bulk
data feed for these records. Outcomes live in per-docket PDFs behind a
JavaScript-driven, bot-resistant portal. That is why comparable products exist
for states with centralized machine-readable court systems and not here, and
it is why the acquire and parse layers are the moat as well as the cost.

## Acquisition policy

- **Real browser.** Playwright with Chromium, because the portal is JS driven
  and resists plain HTTP.
- **Cache first.** Every fetched PDF lands in `data/raw/` and is recorded in
  `raw_dockets`. A docket on disk is never refetched.
- **Slow on purpose.** A randomized delay between `MIN_DELAY` and `MAX_DELAY`
  seconds separates requests. The request rate stays low out of respect for
  the courts' systems and their terms of use. Aggressive scraping gets the
  client blocked and puts the whole project at risk.
- **Owner-directed runs only.** The portal is never contacted except in runs
  the owner explicitly directs (workspace rule). Writing acquisition code and
  executing it against the portal are separate events.
- **Parser first.** The parser is built and validated on a small set of
  manually downloaded dockets before the scraper scales, so progress is never
  blocked on acquisition.
- **Fallback.** If automated access is blocked, the alternative path is a
  formal bulk data request to the Administrative Office of Pennsylvania
  Courts.
- **Window.** Systematic collection covers filings 2023 forward
  (DECISIONS.md D-16), enumerated by year and sequence, growing forward
  indefinitely and extendable backward by config alone.

## Anatomy of a docket sheet

A Common Pleas criminal docket sheet is a multi-page PDF with labeled
sections. The ones the parser cares about, in the order they appear:

1. **Caption and header.** Docket number, court, caption. Repeats on every
   page; the parser reads it once and uses it to stitch continuation pages.
2. **Case Information.** Judge assigned (often the calendar judge, sometimes
   blank or a trial commissioner), date filed, OTN, initiation date.
3. **Status Information.** Case status (Active, Closed, etc.) and status
   history.
4. **Defendant Information.** Name, date of birth, city, state, zip. Read for
   the hash only: name plus year of birth are hashed with the salt in memory
   and discarded. Nothing from this section is ever stored raw.
5. **Charges.** A table of the charges filed: sequence, original sequence,
   grade, statute, statute description, offense date, OTN. Amended and added
   charges appear as additional rows, which is what lets the charge reduction
   analysis work without a separate amendments table.
6. **Disposition Sentencing / Penalties.** The heart of the sheet. Grouped by
   disposition event (for example "Guilty Plea - Negotiated" on a date), each
   event lists the charges it resolved with their offense disposition and
   grade, and for sentenced charges: the **sentencing judge**, sentence date,
   and one or more sentence components (type such as Confinement or
   Probation, a program period, and a min-max length like "Min of 11 Months
   15 Days, Max of 23 Months").
7. **Attorney Information.** Commonwealth and defense counsel. Parsed but not
   yet loaded; parked for a possible future surface (ROADMAP).
8. **Entries.** The chronological docket entries. Not parsed in v1.

## Parser field mapping

| Docket section | Field | Lands in |
|---|---|---|
| Header | docket number | cases.docket_number |
| Case Information | judge assigned | cases.assigned_judge_raw |
| Case Information | date filed | cases.filed_date |
| Case Information | OTN | cases.otn |
| Status Information | case status | cases.case_status |
| Defendant Information | name + DOB year | defendants.id (hash only, then discarded) |
| Charges | seq, grade, statute, description | charges.sequence, .grade, .statute, .offense |
| Disposition section | offense disposition text | charges.disposition_raw (category derived at load) |
| Disposition section | disposition date | charges.disposition_date |
| Disposition section | sentencing judge | charges.disposition_judge_id (via alias resolution); modal judge to cases.judge_id |
| Disposition section | sentence components | sentences.* (one row per component) |

## Known quirks the parser must survive

- **Judge name variants.** "Example, A.", "A. Example", and "Judge Anne
  Example" are one person. Resolution happens in the loader via the alias
  table and override map (DATABASE.md).
- **Multi-component sentences.** Confinement plus consecutive probation on one
  charge is routine. Each component is its own sentences row.
- **Length arithmetic.** Lengths mix units ("11 Months 15 Days"). The parser
  converts to days with a documented rule (month = 30 days, year = 365) and
  keeps the raw text in sentences.raw_text.
- **Continuation pages.** Sections split across pages with repeated headers.
- **Legacy dockets.** Older cases migrated from prior systems can carry
  thinner or oddly formatted data. The parser records what it can and flags
  the docket in raw_dockets.notes rather than failing.
- **Pending cases.** Open cases have charges with no disposition. They load
  normally and are excluded from outcome denominators (METHODOLOGY.md).

## Confirmed by the phase 3 fixture set

- **Decimal quantities in sentence lengths.** Real dockets print
  "Min of 11.00 Months 15.00 Days"; to_days handles decimals (confirmed:
  345/690 days for an 11 1/2 to 23 month sentence).
- **Disposition variants.** "ARD - County" appears alongside bare "ARD";
  the disposition map matches exact strings only, never substrings ("Not
  Guilty" contains "Guilty"). Occasional concatenated multi-part
  disposition strings occur and fall to `other` by design.
- **OTNs can contain spaces** ("U 268081-2" style); stored as printed.
- **Case status values observed:** Closed, Active, Inactive.
- **Judge names arrive clean.** All fixture sentencing judges print as
  "Last, First M." with zero variants observed; alias resolution starts
  easy and the override map stays empty until reality demands otherwise.
- **Portal DOM has no label tags.** Search controls are located by title
  and name attributes, not labels; the docket sheet link carries a one-time
  hash and must be fetched inside the same browser session.

## Secondary source, parked

Court Summary reports (also on the portal) carry a person's county-by-county
case history and support prior record context. Out of scope for v1; noted in
ROADMAP and as a future defendants column in DATABASE.md.