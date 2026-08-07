# FlowForge Data Format

**Schema version:** 1
**Design rule:** an experiment directory must be fully understandable with a text editor and a
spreadsheet, by someone who does not have FlowForge installed.

Format decisions are justified in [ADR-0006](adr/0006-run-directory-csv-json.md) (why a
directory of CSV+JSON rather than a database or Parquet) and
[ADR-0009](adr/0009-store-raw-counts-alongside-si.md) (why raw ADC counts are stored).

---

## 1. Run directory

```text
experiments/
└── 2026-08-07_142233_sphere-25mm/
    ├── request.yaml            # the user's config, byte-for-byte as supplied
    ├── run.yaml                # fully resolved config: defaults filled, refs pinned
    ├── metadata.json           # who, when, what hardware, what software
    ├── calibration.json        # snapshot of every calibration record actually used
    ├── specimen.json           # snapshot of the specimen record
    ├── manifest.json           # schema version + sha256 of every other file
    ├── raw/
    │   ├── samples.csv         # every sample, append-only, never rewritten
    │   ├── events.jsonl        # state transitions, commands, faults, warnings
    │   ├── clocksync.jsonl     # every ping exchange + the fitted clock model
    │   └── phases.csv          # time ranges → (point_id, phase)
    ├── processed/
    │   └── points.csv          # one row per test point, wide format
    ├── results/
    │   ├── summary.json        # headline results with uncertainty + provenance
    │   ├── report.md           # generated human-readable report
    │   └── plots/
    │       ├── drag-vs-speed.png
    │       ├── cd-vs-reynolds.png
    │       ├── force-timeseries.png
    │       └── stability.png
    └── logs/
        └── flowforge.log       # host application log
```

Run id: `YYYY-MM-DD_HHMMSS_<slug>`, local time, slug from the experiment name. Collisions get
`_2`, `_3`. It sorts chronologically in a file listing, which is worth more than a UUID.

### 1.1 The reproducibility contract

> Everything under `processed/` and `results/` is a **pure function** of
> `raw/samples.csv` + `raw/phases.csv` + `run.yaml` + `calibration.json`.

`flowforge analyze <run>` recomputes them from scratch. Consequences:

- A calibration error found later can be corrected retroactively: replace
  `calibration.json`, re-run `analyze`, get corrected results from data recorded months ago.
  This is only possible because raw ADC counts are stored (§3).
- Re-analysis with a newer FlowForge writes a *new* `results/` and appends an entry to
  `metadata.json.analyses[]`. It never edits `raw/`.
- `raw/` is opened append-only during a run and is chmod-ed read-only when the run closes.

---

## 2. `request.yaml` and `run.yaml`

`request.yaml` is the user's file, copied verbatim. `run.yaml` is what FlowForge actually
executed: every default made explicit, every reference resolved to a concrete id and hash.

```yaml
schema_version: 1
name: sphere-25mm-drag

specimen:
  ref: specimens/sphere-25mm.yaml        # resolved copy lands in specimen.json
  revision: "b"

sweep:
  parameter: airspeed                    # airspeed | fan_duty | angle (V2)
  start: 4.0
  end: 18.0
  step: 2.0
  order: ascending                       # ascending | descending | interleaved | randomised
  repeats: 1

measurement:
  stabilization_seconds: 8.0
  stabilization_check:                   # optional; fixed wait alone is the V0 default
    enabled: true
    max_speed_cv: 0.02                   # coefficient of variation of airspeed
    window_seconds: 3.0
    timeout_seconds: 30.0
  sample_seconds: 12.0
  sample_rate_hz: 80                     # requested; achieved rate is recorded
  interleave_zero: false

baseline:
  mode: reference                        # none | reference | inline
  ref: experiments/2026-08-07_131500_fixture-only

analysis:
  blockage_correction: none              # none | maskell
  despike: hampel
  reference_area_source: specimen        # specimen | explicit

safety:
  max_fan_duty: 0.90
  abort_on_overload: true

# --- fields below are added by FlowForge when resolving ---
resolved:
  flowforge_version: "0.4.0"
  flowforge_git: "9f2c1ab"
  request_sha256: "e3b0c442…"
  seed: 20260807142233                   # simulator runs only
```

Validation is by pydantic; an invalid config fails in `VALIDATING`, before the device is
touched. Unknown keys are an error, not a warning — a typo in `stabilization_seconds` must not
silently fall back to a default.

---

## 3. `raw/samples.csv`

**Long (tidy) format.** One row per sample per channel. Justification: channels run at
different rates (80 / 50 / 10 / 1 Hz), and V1 adds a lift channel. Wide format would force
either resampling — destroying the raw record — or a sparse matrix of blanks.

```csv
t_dev_us,channel,seq,raw,si,status
123456789,force.drag,4412,8421031,0.1731,0
123456801,force.drag,4412,8421044,0.1734,0
123456800,dp,881,,14.93,0
123457000,env.t_c,301,,22.31,0
123457000,env.p_pa,301,,100812.4,0
123457000,env.rh,301,,0.412,0
123457000,fan.tach,77,,41.2,0
```

| Column | Type | Notes |
| --- | --- | --- |
| `t_dev_us` | int | Device monotonic microseconds. **The timebase.** Sorted ascending within a channel; not necessarily globally sorted. |
| `channel` | str | Exactly as advertised in the device `hello`. |
| `seq` | int | Per-channel batch sequence from the device. Gaps ⇒ dropped batches. |
| `raw` | int \| empty | Uncalibrated device units (ADC counts). Empty where the sensor has no meaningful raw domain. |
| `si` | float | SI value. For `force.*` this is the **device's advisory** figure and is *not* what analysis uses. |
| `status` | int | Status bitfield from [device-protocol.md §5.3](device-protocol.md#53-fields). |

**The force column that matters is `raw`, not `si`.** Analysis computes
`F = (raw − zero(t)) / slope` using `calibration.json`. Storing counts is what makes
retroactive recalibration possible; storing only newtons would permanently bake in whatever
calibration happened to be loaded that day.

Typical size: a 8-point sweep with 12 s windows and 8 s stabilisation is ≈ 200 s of streaming
≈ 30 000 rows ≈ 1.5 MB. Gzip on close is a config option; CSV is kept plain by default because
grep-ability is the point.

---

## 4. `raw/phases.csv`

Maps time ranges to what the engine was doing. Keeps `samples.csv` a pure sensor record while
staying hand-inspectable.

```csv
t_start_us,t_end_us,phase,point_id,detail
100000000,104200000,ZEROING,,pre-sweep tare
104200000,112300000,STABILISING,p01,target 4.0 m/s duty 0.28
112300000,124300000,SAMPLING,p01,
124300000,132100000,STABILISING,p02,target 6.0 m/s duty 0.36
```

`phase` ∈ the experiment state machine's states. Re-analysis may legitimately choose a
*different* window inside a `SAMPLING` phase (for example, trimming the first 2 s); the
original window is preserved here so the two can be compared.

---

## 5. `raw/events.jsonl`

One JSON object per line, appended in real time, flushed immediately. Written **before** the
action it describes, so a crash leaves evidence of what was attempted.

```jsonl
{"t_dev_us":100000000,"t_host":"2026-08-07T14:22:33.412+02:00","src":"host","kind":"state","from":"CONNECTING","to":"ZEROING"}
{"t_dev_us":104100000,"t_host":"…","src":"host","kind":"command","cmd":"set_fan","args":{"duty":0.28},"req":31}
{"t_dev_us":104110000,"t_host":"…","src":"device","kind":"ack","req":31,"data":{"duty":0.28}}
{"t_dev_us":118900000,"t_host":"…","src":"host","kind":"warning","code":"ZERO_DRIFT","detail":{"drift_n":0.0021,"threshold_n":0.0020}}
{"t_dev_us":132000000,"t_host":"…","src":"device","kind":"event","evt":"fault","fault":"TACH_STALL"}
```

`src` is `host` or `device`. Device messages are recorded verbatim with the device's own `t`.
Host-originated events carry the device timestamp implied by the clock model *and* the host
wall-clock, clearly distinguished.

Warning and error `code` values are a closed enum shared with `summary.json`.

---

## 6. `raw/clocksync.jsonl`

```jsonl
{"kind":"ping","t_send_host":1786…,"t_dev":123456789,"t_recv_host":1786…,"rtt_us":1420,"used":true}
{"kind":"fit","at_t_dev":140000000,"alpha":1.0000173,"beta":1786234953.114,"residual_mad_us":180,"n":42}
```

Present so that a reader can reconstruct or reject the device→host time mapping independently.
Nothing in the analysis path depends on it.

---

## 7. `calibration.json`

A **snapshot**, not a reference. The calibration store may change; the run must not.

```json
{
  "schema_version": 1,
  "records": [
    {
      "id": "loadcell-drag-2026-08-01-a",
      "channel": "force.drag",
      "kind": "load_cell_force",
      "created": "2026-08-01T10:14:00+02:00",
      "operator": "min",
      "model": "linear",
      "slope_counts_per_N": 48213.7,
      "slope_u_counts_per_N": 402.1,
      "intercept_counts": 8420115.0,
      "r_squared": 0.99987,
      "residual_max_frac_fs": 0.0031,
      "points": [
        {"applied_N": 0.0,      "counts": 8420115, "counts_sd": 41},
        {"applied_N": 0.049033, "counts": 8422479, "counts_sd": 44}
      ],
      "method": "horizontal load at specimen station via pulley, calibrated masses",
      "masses_traceability": "OIML M1 class, 5 g / 10 g / 20 g",
      "temperature_c": 21.4,
      "notes": "lever ratio and pivot friction folded into slope by design"
    },
    {
      "id": "pitot-2026-08-03-a",
      "channel": "dp",
      "kind": "pitot_factor",
      "k": 0.983,
      "k_u": 0.019,
      "method": "comparison against hot-wire anemometer at test-section centreline",
      "reference_instrument": "Testo 405i, cal 2026-02"
    }
  ],
  "tare": {
    "channel": "force.drag",
    "zero_pre_counts": 8420098.4,
    "zero_pre_t_dev_us": 102000000,
    "zero_post_counts": 8420131.9,
    "zero_post_t_dev_us": 331000000,
    "zero_return_N": 0.00069,
    "model": "linear_interpolation"
  }
}
```

A run whose `calibration.json` lacks a record for a channel used in analysis fails in
`VALIDATING` with `CALIBRATION_MISSING`. A record older than `calibration.max_age_days`
produces a loud warning that is reprinted in the report; it does not silently pass.

---

## 8. `specimen.json`

```json
{
  "schema_version": 1,
  "id": "sphere-25mm",
  "revision": "b",
  "name": "Sphere, 25 mm",
  "geometry": {
    "reference_area_m2": 4.9087e-4,
    "reference_area_source": "computed from measured diameter",
    "characteristic_length_m": 0.025,
    "measured_dimensions_mm": {"diameter": 25.02, "diameter_u": 0.15},
    "frontal_blockage_ratio": 0.0491
  },
  "manufacturing": {
    "method": "FDM",
    "material": "PLA",
    "printer": "Prusa MK4",
    "layer_height_mm": 0.15,
    "post_processing": "sanded to 400 grit, primer filled"
  },
  "mass_kg": 0.0091,
  "files": {
    "stl": "hardware/cad/specimens/sphere-25mm-revb.stl",
    "source": "hardware/cad/specimens/sphere-25mm-revb.scad",
    "sha256": {"stl": "7a1f…", "source": "c04d…"}
  },
  "parameters": {"diameter_mm": 25.0},
  "notes": "surface finish matters at these Reynolds numbers; see docs/measurement-model.md §10"
}
```

`parameters` is a free-form dictionary. It is unused in V0 and is the hook that makes V6
parametric optimisation possible without a format change.

`reference_area_source` distinguishes a nominal CAD area from one computed from measured
dimensions. The first is `ASSUMED`, the second `MEASURED`. This changes the provenance tag on
`Cd` and is not cosmetic.

---

## 9. `processed/points.csv`

Wide format — one row per test point. This is the file a human opens in a spreadsheet.

```csv
point_id,ordinal,repeat,requested_speed_mps,fan_duty,t_start_us,t_end_us,
n_samples,n_rejected,n_eff,dropout_frac,
force_raw_mean_N,force_raw_sd_N,force_fixture_N,force_N,force_u_N,
dp_mean_Pa,dp_sd_Pa,dp_u_Pa,
temp_C,press_Pa,rh,rho_kg_m3,rho_u,
v_mps,v_u_mps,q_Pa,cd,cd_u,cd_blockage_corrected,re,
tach_hz,speed_cv,warnings
```

| Group | Columns | Meaning |
| --- | --- | --- |
| identity | `point_id`, `ordinal`, `repeat` | `p01`, `p02`… stable across re-analysis |
| setpoint | `requested_speed_mps`, `fan_duty` | what was asked for, and the duty used |
| window | `t_start_us`, `t_end_us` | on the device clock |
| quality | `n_samples`, `n_rejected`, `n_eff`, `dropout_frac`, `speed_cv` | see [measurement-model.md §7](measurement-model.md#7-statistics-over-a-sample-window) |
| force | `force_raw_mean_N` … `force_u_N` | raw (tared) → fixture-subtracted → uncertainty |
| flow | `dp_*`, `v_mps`, `v_u_mps`, `q_Pa` | measured Δp and derived speed |
| environment | `temp_C`, `press_Pa`, `rh`, `rho_kg_m3` | as measured; `rho` derived |
| aerodynamics | `cd`, `cd_u`, `cd_blockage_corrected`, `re` | `cd_blockage_corrected` empty when correction is off |
| flags | `warnings` | `;`-separated warning codes for this point |

Both `force_raw_mean_N` and `force_N` are present. The intermediate is never discarded.

---

## 10. `results/summary.json`

The machine-readable headline. Every reported quantity is an object, never a bare float.

```json
{
  "schema_version": 1,
  "run_id": "2026-08-07_142233_sphere-25mm",
  "status": "COMPLETED",
  "specimen": {"id": "sphere-25mm", "revision": "b"},
  "conditions": {
    "temperature_C": {"value": 22.3, "u": 0.5, "unit": "degC", "provenance": "MEASURED"},
    "pressure_Pa":   {"value": 100812, "u": 100, "unit": "Pa", "provenance": "MEASURED"},
    "relative_humidity": {"value": 0.41, "u": 0.03, "unit": "1", "provenance": "MEASURED"},
    "air_density":   {"value": 1.187, "u": 0.003, "unit": "kg/m3", "provenance": "DERIVED",
                      "formula": "moist ideal gas, measurement-model.md §3.2"}
  },
  "geometry": {
    "reference_area": {"value": 4.9087e-4, "u": 7.9e-6, "unit": "m2", "provenance": "MEASURED"},
    "blockage_ratio": {"value": 0.0491, "unit": "1", "provenance": "DERIVED"}
  },
  "fit": {
    "power_law": {
      "exponent": {"value": 1.97, "u": 0.05, "unit": "1", "provenance": "DERIVED"},
      "expected": 2.0,
      "comment": "F = a·v^n; n consistent with v-squared scaling"
    }
  },
  "aggregate": {
    "cd_mean": {"value": 0.471, "u": 0.047, "unit": "1", "provenance": "DERIVED",
                "coverage_factor": 2, "method": "inverse-variance weighted mean over points with Re > 1e4",
                "inputs": ["force", "dp", "reference_area", "pitot_factor"]},
    "reynolds_range": {"min": 6600, "max": 29800, "provenance": "DERIVED"}
  },
  "calibration_used": [
    {"id": "loadcell-drag-2026-08-01-a", "age_days": 6, "expired": false},
    {"id": "pitot-2026-08-03-a", "age_days": 4, "expired": false}
  ],
  "quality": {
    "zero_return_N": 0.00069,
    "max_dropout_frac": 0.0012,
    "points_flagged": 1,
    "baseline_run": "2026-08-07_131500_fixture-only"
  },
  "warnings": [
    {"code": "HIGH_BLOCKAGE", "detail": "S/C = 4.9% approaches the 5% guideline"},
    {"code": "SNR_MARGINAL", "point": "p01", "detail": "F = 2.3 mN vs u(F) = 1.1 mN"}
  ],
  "claims_not_supported": [
    "absolute Cd better than ±15% (turbulence intensity unmeasured)"
  ]
}
```

The `Quantity` object shape — `{value, u, unit, provenance}` plus optional `coverage_factor`,
`formula`, `method`, `inputs` — is used everywhere a number is reported. There is no code path
that writes a bare float into `summary.json`.

`claims_not_supported` is generated, not hand-written. It is the machine-readable form of the
honesty requirement in [measurement-model.md §10](measurement-model.md#10-what-v0-can-and-cannot-claim).

---

## 11. `metadata.json`

```json
{
  "schema_version": 1,
  "run_id": "2026-08-07_142233_sphere-25mm",
  "started": "2026-08-07T14:22:33.412+02:00",
  "ended": "2026-08-07T14:29:11.882+02:00",
  "operator": "min",
  "host": {"os": "macOS 15.6", "python": "3.13.2", "hostname": "…"},
  "flowforge": {"version": "0.4.0", "git": "9f2c1ab", "dirty": false},
  "device": {
    "device_id": "ff-esp32-0A1B2C", "fw_version": "0.3.1", "fw_git": "a1b2c3d",
    "board": "flowforge-ctrl-rev-a", "proto": 1, "reset_reason": "POWERON"
  },
  "tunnel": {"config_ref": "hardware/configs/tunnel-rev-a.yaml", "test_section_m2": 0.01},
  "backend": "serial",
  "achieved_rates_hz": {"force.drag": 79.94, "dp": 49.98, "env": 1.00},
  "analyses": [
    {"at": "2026-08-07T14:29:12+02:00", "flowforge": "0.4.0", "results_hash": "5c1d…"}
  ]
}
```

`"backend": "sim"` appears for simulated runs, together with the plant-model parameters and
the seed. A simulated run is never mistakable for a physical one, in the directory or in the
report header.

---

## 12. `manifest.json`

```json
{
  "schema_version": 1,
  "created_by": "flowforge 0.4.0",
  "files": {
    "run.yaml":        {"sha256": "…", "bytes": 1842},
    "raw/samples.csv": {"sha256": "…", "bytes": 1523118, "rows": 30412},
    "raw/events.jsonl":{"sha256": "…", "bytes": 9214, "lines": 118}
  },
  "raw_frozen": true
}
```

`flowforge verify <run>` recomputes every hash. It is the check that a run directory has not
been silently edited — which matters the moment results are shared or published.

---

## 13. Schema evolution

- Every file carries `schema_version`.
- Readers accept their own version and all older ones; migration functions live in
  `flowforge.storage.migrations` and are exercised by golden-file tests against fixture runs
  checked into `tests/fixtures/runs/`.
- Adding a **column** to `samples.csv` or `points.csv` is a minor change: readers key by
  column name, never by index.
- Adding a **channel** is not a schema change at all — it is more rows. This is why the lift
  axis in V1 costs nothing here.
- Parquet is a future *addition*, not a replacement: `flowforge convert <run> --parquet` will
  emit `raw/samples.parquet` alongside the CSV. The CSV remains canonical for as long as
  inspectability outranks size. See [ADR-0006](adr/0006-run-directory-csv-json.md).
