# ADR-0009 — Raw ADC counts are stored; calibration is applied only on the host

**Status:** Accepted · 2026-08-07

## Context

The load cell produces ADC counts. A calibration record converts counts to newtons. The obvious
design has the firmware apply the calibration and stream newtons: less host work, smaller
messages, and a device that reports meaningful units.

Load-cell calibrations are, however, the thing most likely to be wrong — a mistyped mass, a
mid-calibration bump, a fit accepted on five clustered points, a slipped clamp discovered a week
later. And the requirements demand that experiments be reproducible and re-analysable.

## Decision

The firmware **never applies calibration**. It streams integer ADC counts in the `raw` field
and, where it is cheap and meaningful, an advisory SI value in `si` with `si_valid: false`
declared in the channel descriptor.

The host stores **both** in `raw/samples.csv` and derives force exclusively from `raw` using the
calibration record snapshotted into the run's `calibration.json`.

Corollaries:

- There is no `tare` or `calibrate` command in the wire protocol. Taring is host-side arithmetic
  over streamed counts.
- Nothing in the firmware needs reflashing when a calibration changes.
- Digitally-calibrated sensors that produce SI natively (SDP810 → Pa, BME280 → °C/Pa/RH) declare
  `si_valid: true` and have no meaningful raw domain; their `raw` column is empty.

## Alternatives considered

**Firmware applies calibration, streams newtons.** Smaller host, self-describing device — and
it permanently bakes a possibly-wrong constant into the only record that exists. Recovering
from a bad calibration would require the original counts, which would no longer exist. This
single consideration decides it.

**Store only counts, no SI at all.** Purer, and the file becomes unreadable to a human without
running FlowForge — contradicting [ADR-0006](0006-run-directory-csv-json.md). The advisory SI
column costs a few bytes and makes the raw file browsable.

**Store counts and a *reference* to the calibration record.** Fragile: the calibration store is
mutable, the run must not be. Hence a full snapshot, not a reference.

## Consequences

**Good**

- A calibration error found later is fully recoverable: replace `calibration.json`, re-run
  `flowforge analyze`, and get corrected results from data recorded months earlier. This is
  tested directly — M5 acceptance criterion 6 asserts that a 10 % slope change produces exactly
  a 10 % force change.
- Integer counts round-trip exactly through JSON and CSV; no float text precision loss on the
  one channel where it would matter most.
- Calibration is a data problem, not a firmware-deployment problem.

**Bad, and accepted**

- Two columns for one quantity invites reading the wrong one. Mitigated by `si_valid: false` in
  the channel descriptor, by the column being documented as advisory, and by the analysis code
  path having no access to `si` for force channels at all.
- A run whose `calibration.json` is lost or corrupted yields counts nobody can interpret. The
  manifest hashes it; the snapshot lives inside the run directory rather than beside it.
- The device's own display of force (in a `status` command, say) can disagree with FlowForge's.
  Accepted — the device's figure is explicitly labelled advisory, and disagreement is a useful
  signal that a calibration has changed.
