# Decisions

> Status: living log. Locked decisions are settled; reopening one requires a
> new entry superseding the old, not an edit. Agents: do not relitigate locked
> entries. Last updated 2026-07-02.

## Locked

**D-01 Jurisdiction: Philadelphia (2026-07-02).** The judge is recoverable
from CP docket sheets, the niche is open, and a strong local research base
exists to check findings against.

**D-02 Own dataset from public dockets (2026-07-02).** Coverage and freshness
stay in our control rather than depending on a third party snapshot.
Pennsylvania has no public bulk feed, so the acquire and parse layers are both
the cost and the moat.

**D-03 Judge dimension central (2026-07-02).** The single largest source of
sentencing variance, and the dimension comparable defendant-facing tools omit.
The closest comparable profiles the officer, the defense attorney, and the
prosecutor: everyone around the bench except the person on it, and its own
data cannot reliably support judges. Ours can.

**D-04 Name: CP51 (2026-07-02).** Named for the prefix on every Philadelphia
Common Pleas criminal docket. Tagline: "What actually happens in Philadelphia
criminal court." Chosen over PhillyCourtFile (reads as a franchise and quietly
promises record lookup), The Going Rate, and BenchMark. Owner action still
open: domain and trademark check (O-1).

**D-05 Privacy by construction, aggregates-only publication (2026-07-02).**
No defendant names or DOBs at rest anywhere; persons exist only as salted
hashes. The public product publishes aggregates only: no per-case pages, no
docket numbers, nothing about any individual defendant. Judges, as public
officials acting publicly, are named, but only next to numbers that clear the
thresholds. Juvenile and non-public matters are out of scope entirely.

**D-06 Descriptive distributions over a predictive black box (2026-07-02).**
More honest, more interpretable, more defensible, easier to build. The
calibration backtest is the honest form of the predictive ambition.

**D-07 Threshold-plus-interval regime (2026-07-02).** Minimum-n thresholds
(page 20, metric 30, judge 40, initial values) borrowed from the comparable's
proven suppression discipline, then extended with Wilson intervals and partial
pooling, which the comparable lacks entirely. Thresholds enforced in the stats
release builder, not the client.

**D-08 SQLite now, Postgres on Neon later, Alembic only then (2026-07-02).**
Zero-setup single file that the analysis stack reads directly. Pre-data schema
changes happen by editing schema.py and re-initializing.

**D-09 Precomputed stats release plus read-only API (2026-07-02).** The
serving layer reads versioned JSON artifacts and never touches the database.
FastAPI penciled, contract framework agnostic. Full contract designed up front
(API.md) because it defines what phase 5 must produce.

**D-10 Schema v2 (2026-07-02).** Four changes folded in before any data
exists: sentences one-to-many with charges; disposition_raw preserved plus
derived disposition_category; sentencing judge captured at the disposition
event (charges.disposition_judge_id) with cases.judge_id as the modal
convenience; charge_categories plain-language taxonomy. DATABASE.md is
authoritative; the build spec's schema is superseded.

**D-11 Charge-grain analysis (2026-07-02).** Case-level sentence totals
require concurrency structure dockets state inconsistently; out of scope for
v1 rather than approximated.

**D-12 Information, not legal advice; no lead generation (2026-07-02).** The
disclaimer ships inside the API payload. The comparable's attorney lead-gen
revenue model is explicitly not copied; it sits badly next to the framing.

**D-13 Comparable reference: virginiacourtfile.com (2026-07-02).** Borrowed:
suppression thresholds, denominator hygiene, plain-language charge taxonomy,
the name-aliasing playbook (repurposed for judges), case duration as a
headline metric, the trust apparatus (methodology page, as_of stamps,
corrections process). Not borrowed: officer profiles, lead generation, raw
rates without intervals. Structural differences: their substrate is a
centralized state data system, ours is per-docket PDFs; their named entity is
the officer, ours is the judge.

**D-14 Documentation conventions (2026-07-02).** No em dashes anywhere in the
repo. Every doc opens with a status header separating built from target
design, because these docs double as agent context. All examples are
synthetic: docket CP-51-CR-0000000-2024, fictional judges surnamed Example.
README stays short and defers to docs/.

**D-15 Parser before scraper; portal runs owner-directed only (2026-07-02).**
The parser is validated on hand-collected dockets first. The live portal is
contacted only in runs the owner explicitly directs, always with the
randomized delay, never refetching cached dockets.

## Open

**O-1 Domain and trademark check for CP51.** Owner action before public use of
the name.

**O-2 Judge confinement-rate estimator.** v1 is empirical Bayes beta-binomial
shrinkage (transparent, fits the stack). Decide in phase 5 whether a logistic
mixed model is warranted, which may pull in an extra dependency.

**O-3 Collection window.** Proposed: filings 2019 through present, giving
pre- and post-pandemic cohorts. Confirm before phase 2 scales.

**O-4 Repo rename.** The build spec says `phl-sentencing-forecaster`; the
project is now CP51. Recommend creating the repo as `cp51` before the first
push so the name never has to migrate.

**O-5 License.** Undecided. Decide before the repo ever goes public; private
until then.

**O-6 Corrections process wording.** The public site needs a data-corrections
contact and policy page (part of the trust apparatus). Draft in phase 6.