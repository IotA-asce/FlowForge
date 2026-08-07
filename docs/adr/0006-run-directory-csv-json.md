# ADR-0006 — Experiments are directories of CSV + JSON, not a database

**Status:** Accepted · 2026-08-07

## Context

Each run produces configuration, metadata, calibration snapshots, tens of thousands of raw
samples, per-point aggregates, results, and plots. Runs must be comparable, archivable,
shareable, and — critically — re-analysable years later.

The requirements state that experiments must remain inspectable without FlowForge.

## Decision

One directory per run, containing plain CSV and JSON, laid out per
[data-format.md](../data-format.md). Raw samples are stored in **long (tidy) format**: one row
per sample per channel.

A `manifest.json` records the SHA-256 of every file; `raw/` is opened append-only during the run
and made read-only at close.

## Alternatives considered

**SQLite.** Single file, real queries, transactional, and genuinely tempting. Rejected because
the requirement is that a stranger can open the data with a spreadsheet, and because the
project's most valuable artefact is a *published* experiment whose raw data anyone can check.
SQLite is also worse for git and for diffing two runs. It remains the obvious answer if
cross-run querying ever becomes a real workflow, and importing a directory tree into SQLite is
straightforward.

**Parquet now.** Roughly 10× smaller and far faster to load. At 1.5 MB per run, neither matters
yet, and it costs binary opacity plus a pyarrow dependency at the exact layer that must stay
trivially readable. Deferred as an *addition*: `flowforge convert --parquet` will emit
`raw/samples.parquet` alongside the CSV, with CSV remaining canonical.

**HDF5 / NetCDF.** The scientific-instrument default, with real self-describing metadata.
Rejected for tooling weight and poor inspectability with ordinary tools.

**Wide-format CSV** (one column per channel, one row per timestamp). Easier to open in a
spreadsheet, but channels run at 80/50/10/1 Hz, so wide format forces either resampling — which
destroys the raw record the whole design is built to preserve — or a sparse grid of blanks. And
V1's lift channel would change the schema, whereas in long format it is simply more rows.

## Consequences

**Good**

- Zero-dependency inspection: `head`, `grep`, `awk`, Excel, pandas.
- Git-friendly for small canonical example runs committed to `examples/`.
- Sharing a result is `zip` and send, with the manifest proving nothing was edited.
- Adding a channel is not a schema change.

**Bad, and accepted**

- Long format is awkward to eyeball. Mitigated by `processed/points.csv` being wide — the file
  a human actually opens — and by the raw file being pivotable in one pandas call.
- Cross-run queries mean walking directories. Fine at hundreds of runs; the point at which it
  stops being fine is the point at which SQLite becomes the right answer.
- CSV has no types. Column semantics are pinned in [data-format.md §3](../data-format.md#3-rawsamplescsv)
  and enforced by readers, with `schema_version` in every sibling file.
- Float text costs precision and space. Handled by storing force as integer counts
  ([ADR-0009](0009-store-raw-counts-alongside-si.md)) and formatting other columns with enough
  digits to round-trip.
