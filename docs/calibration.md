# FlowForge Calibration

Calibration is a first-class feature, not a constant in a header file. Nothing in the FlowForge
source tree contains a sensor scale factor. Every conversion from device units to SI goes
through a stored, dated, identified calibration record, and the records actually used are
snapshotted into each run directory.

Related: [measurement-model.md](measurement-model.md) for what the constants mean,
[data-format.md §7](data-format.md#7-calibrationjson) for the on-disk schema.

---

## 1. Store layout

```text
calibration/
├── index.json                              # channel → active record id
├── loadcell-drag-2026-08-01-a.json
├── loadcell-drag-2026-06-14-a.json         # superseded, retained
├── pitot-2026-08-03-a.json
├── fan-map-tunnel-rev-a-2026-08-02.json
└── env-offset-2026-07-30.json
```

Rules:

- Records are **immutable once written**. A re-calibration creates a new record; it never edits
  an old one. Superseded records stay on disk forever — they are the only way to re-derive an
  old run's original numbers.
- `index.json` names the active record per channel. It is the only mutable file.
- Every record has `id`, `channel`, `kind`, `created`, `operator`, `method`, `instrument`
  (what reference was used), `temperature_c`, and its fit parameters with uncertainties.
- `flowforge calibration list` prints active records, ages, and expiry status.

Expiry is advisory, not enforced: `calibration.max_age_days` (default 90) produces a warning
that appears in the run summary and the report header. Enforcing it would tempt people to
back-date; surfacing it makes the choice visible in the published record.

---

## 2. Load-cell force calibration

This is the most important calibration in the system and the one most often done wrong.

### 2.1 Principle

Do **not** calibrate the load cell as a load cell and then multiply by a measured lever ratio.
Calibrate the *whole balance*, end to end, by applying **known horizontal forces at the
specimen station** — the exact point and direction where drag will act.

That single choice folds the lever ratio, pivot friction, flexure stiffness, and the small
gravity-restoring term into one empirically measured slope. No geometry is measured with a
ruler and trusted in software.

```text
                 ═══ pivot
                     │
                     ├──► load cell
                     │
                     │
      specimen ──►┌──┴──┐        low-friction pulley
      station     │mount│─────────────○
                  └─────┘             │
                                      │  string, in line with the flow axis
                                      │
                                   [ mass m ]
```

### 2.2 Applied force from a mass

```text
F = m · g_local
```

Use **local** gravity, not 9.80665. The international gravity formula plus a free-air
correction is accurate to ~1e-5 g and removes a systematic of up to 0.3 %:

```text
g(φ, h) = 9.780327·(1 + 0.0053024·sin²φ − 0.0000058·sin²2φ) − 3.086e-6·h
```

with latitude `φ` and elevation `h` in metres. FlowForge stores `latitude_deg` and
`elevation_m` in site config and computes `g_local` at calibration time; both go into the
record.

Air buoyancy on the calibration masses is ≈0.015 % for steel and is **deliberately ignored**;
it is an order of magnitude below the mass-set tolerance. This is recorded in the record's
`assumptions` field rather than left implicit.

### 2.3 Procedure

1. Assemble the balance exactly as it will run, including the sting and any fairing. Fan off,
   tunnel closed, no draughts. Let the electronics warm up for **15 minutes** — load-cell zero
   drift is dominated by thermal transients.
2. `flowforge calibrate force --channel force.drag`
3. Record 30 s at zero load → `intercept_counts` and its noise.
4. Apply masses in ascending order, covering the working range. For a 100 g cell on a 3:1
   lever, the drag range 0–130 mN maps to roughly 0–13 gf at the cell; use masses giving
   applied forces of approximately **0, 5, 10, 20, 50, 100, 150 mN**
   (≈ 0.5, 1, 2, 5, 10, 15 g). At each step, wait 10 s, then record 20 s.
5. Repeat the sequence **descending** through the same points. The up/down difference is the
   hysteresis estimate.
6. Return to zero and record 30 s → **zero-return error**.
7. FlowForge fits `counts = intercept + slope · F` by ordinary least squares, weighted by each
   point's sample variance.

### 2.4 Acceptance criteria

The command refuses to write a record unless all hold:

| Criterion | Threshold | Rationale |
| --- | --- | --- |
| `r²` | ≥ 0.9995 | linearity |
| Max residual | ≤ 0.5 % of full scale | catches a single bad point that `r²` hides |
| Hysteresis (max up−down) | ≤ 0.5 % of full scale | catches binding, stiction, loose fasteners |
| Zero return | ≤ 0.2 % of full scale | catches yielding or a slipping clamp |
| Points | ≥ 5 distinct, ≥ 2 above 50 % of range | a fit through three low points is not a calibration |

Failures print *which* criterion failed and the usual physical cause. A hysteresis failure on a
pendulum balance is nearly always the pivot or a rubbing cable, and the message says so.

### 2.5 What gets stored

`slope_counts_per_N` and its standard uncertainty (from the fit covariance combined with the
mass-set tolerance), the intercept, `r²`, max residual, hysteresis, zero return, every raw
point with its sample sd, ambient temperature, `g_local`, mass-set traceability, and free-text
notes. See [data-format.md §7](data-format.md#7-calibrationjson).

`slope_u_counts_per_N` is not decoration — it is a Type B term in every subsequent force
uncertainty.

---

## 3. Tare (zeroing)

Tare is a per-run operation, not a calibration. It measures the current zero offset; it does
not change the slope.

`flowforge tare --seconds 30` and, automatically, the `ZEROING` state at the start of every
run:

1. Confirm fan duty is zero and the tunnel is settled.
2. Record `duration` seconds of counts.
3. Reject spikes (Hampel), then take the mean → `zero_counts`, with its sd.
4. Refuse if the sd exceeds `tare.max_noise_counts`, or if a linear fit over the window shows a
   slope beyond `tare.max_drift_counts_per_s` — a drifting zero means the balance has not
   thermally settled, and taring on top of that guarantees an uncorrectable bias.

A **post-sweep tare** is taken automatically at the end of every run. The pre/post pair drives
the linear zero interpolation and produces the zero-return figure reported in the summary. See
[measurement-model.md §5.3](measurement-model.md#53-zero-handling).

`measurement.interleave_zero: true` inserts a zero point between every speed step. It roughly
doubles run time and is the recommended setting for the validation experiment and for any
comparison where the differences are small.

---

## 4. Airspeed calibration

The quantity calibrated is the dimensionless pitot factor `k` in `v = k·√(2Δp/ρ)`. It enters
`Cd` **squared**, so a 2 % error in `k` is a 4 % error in `Cd`.

Three methods, in descending order of preference:

**A. Reference anemometer (preferred).** A hot-wire or vane anemometer at the test-section
centreline, with the specimen removed. Sweep 4–18 m/s, record simultaneous `Δp` and reference
`v`, fit `v_ref = k·√(2Δp/ρ)` through the origin. Store `k`, `k_u`, the reference instrument's
make and calibration date, and every point.

**B. Volumetric / traverse method.** A 5- or 9-point traverse across the test section with the
same probe, integrated to a mean velocity, compared against the centreline reading. This also
yields the **velocity uniformity** figure, which is worth having on its own and belongs in the
tunnel characterisation record.

**C. Assume `k = 1.0`.** Legitimate for a well-made pitot-static probe aligned with the flow,
and it is the V0 default before a reference instrument is available. FlowForge then tags `k` as
`ASSUMED` with `k_u = 0.06`, and every derived `Cd` becomes `ESTIMATED`. The report says so in
plain language.

Also stored in the airspeed record: the differential-pressure sensor's **zero offset**,
measured with both probe ports open to still room air, and re-measured at the start of every
run (the SDP8xx family drifts by a few tenths of a pascal, which matters at 4 m/s).

---

## 5. Fan duty → speed map

Strictly a *characterisation*, not a calibration, but it is stored the same way because it is
tunnel- and hardware-specific and must be traceable.

`flowforge calibrate fan-map`:

1. Arm, then step duty from `d_min` to `max_duty` in 5 % increments, ascending.
2. At each step wait 10 s, record 10 s of airspeed, tachometer, and Δp.
3. Repeat descending — fan hysteresis is real and the difference is stored.
4. Fit `v_ss(d)` as piecewise-linear over the measured points, and record `d₀`, the duty below
   which flow does not establish.

The experiment engine uses the inverse of this map to *seed* the duty for a requested airspeed,
then verifies against the measured airspeed. In V0 that verification is a check, not a control
loop:

- If `|v_measured − v_requested| > tolerance` after stabilisation, apply **one** proportional
  correction and re-stabilise.
- If it still fails, record the achieved speed, flag `SPEED_OFF_TARGET`, and continue. The
  analysis uses the **measured** speed throughout, never the requested one, so an imperfect map
  degrades the sweep's tidiness but not its correctness.
- If flow cannot be established at all, fail with `SPEED_UNREACHABLE`.

This is the seam where a PID controller lands in a later version, with no change above it.

---

## 6. Environmental sensor check

The BME280 is factory-calibrated and its specified accuracy (±1 °C, ±1 hPa, ±3 % RH) is already
far better than needed — recall from
[measurement-model.md §6.1](measurement-model.md#61-air-density-cancels) that air density
cancels out of `Cd` entirely.

What still matters:

- **Self-heating.** Mount the sensor away from the ESP32 and any regulator, in the flow if
  practical. A 1–2 °C self-heating offset is common and biases `Re` and reported `v`.
- **Offset check.** Compare against any reference thermometer and barometer (a local METAR
  station's QNH corrected for elevation is adequate for pressure) and store a fixed offset
  record if it exceeds the sensor's spec.
- Humidity is the least important channel; a failed RH sensor falls back to 50 % with a
  recorded substitution and a provenance demotion, not a run failure.

---

## 7. Verification, not just calibration

A calibration that is never checked is a belief. Two cheap checks, both CLI commands:

**`flowforge verify force`** — apply one known mass not used in the fit (a "check standard"),
and assert the recovered force lies within the record's stated uncertainty. Run before any
session that matters. Result appended to `calibration/verification-log.jsonl`.

**`flowforge verify repeatability`** — run the same specimen twice, back to back, and report
whether the two `Cd` curves agree within their combined uncertainty. This is the project's
headline success criterion, so it is a command rather than a manual ritual.

---

## 8. Order of operations

```text
mechanical assembly complete
        ↓
15 min warm-up
        ↓
load-cell calibration          (rarely; after any mechanical change)
        ↓
fan duty→speed map             (per tunnel configuration)
        ↓
pitot factor k                 (when a reference anemometer is available)
        ↓
──────── per session ────────
        ↓
verify force with a check mass
        ↓
dp zero offset
        ↓
──────── per run ────────
        ↓
pre-sweep tare  →  sweep  →  post-sweep tare
```

Any mechanical change to the balance — retightening the sting, swapping the fairing, moving the
pivot — **invalidates the load-cell calibration**. FlowForge cannot detect this. The record's
`notes` field and the assembly documentation both say so, and the check-mass verification is
the practical defence.
