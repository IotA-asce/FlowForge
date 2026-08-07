# FlowForge Measurement Model

**Purpose:** state exactly what FlowForge measures, what it derives, what it assumes, and how
big the error bars are. Every formula and every constant used anywhere in the codebase is
defined here. If a number appears in a result, its derivation is on this page.

All quantities are SI unless a unit suffix says otherwise.

---

## 1. Provenance taxonomy

Every quantity in `summary.json` carries one of five tags. This is enforced by the type system
(`flowforge.quantity.Quantity` requires a `provenance` field).

| Tag | Meaning | Example |
| --- | --- | --- |
| `MEASURED` | Comes from a sensor via a calibration record. Nothing else. | drag force, differential pressure, temperature |
| `DERIVED` | Computed from `MEASURED` values by a documented formula. | air density, airspeed, dynamic pressure, `Cd`, `Re` |
| `ESTIMATED` | Computed with a statistical or empirical model that could be wrong in ways the formula does not express. | blockage-corrected `Cd`, fixture-drag correction, stabilisation verdict |
| `ASSUMED` | A constant or default we did not measure this run. | `k_pitot = 1.0` when uncalibrated, sea-level pressure when no BME280 |
| `USER_PROVIDED` | Typed into the config by a human. | reference area, specimen dimensions, material |

A `DERIVED` quantity that consumes an `ASSUMED` input is reported as `ESTIMATED`, not
`DERIVED`. This propagation rule is implemented once, in `flowforge.provenance`.

---

## 2. Reference geometry (V0)

The error budget below depends on the physical scale, so the design point is fixed here.

| Parameter | Value | Note |
| --- | --- | --- |
| Test section | 100 × 100 mm square, 300 mm long | see [BOM](../hardware/BOM.md) |
| Cross-sectional area `C` | 0.0100 m² | |
| Contraction ratio | 4 : 1 from a 200 × 200 mm settling chamber | reduces turbulence intensity |
| Speed range | 4 – 18 m/s | lower bound set by pitot SNR, upper by fan array |
| Specimen characteristic size | 25 mm | |
| Blockage ratio `S/C` | 4.9 % (sphere) – 6.25 % (cube) | above the ideal 5 %; see §8 |

The 25 mm specimen size is a deliberate compromise: smaller specimens reduce blockage error
but shrink the force signal quadratically. A 20 mm variant (3.1 – 4.0 % blockage, 36 % less
force) is documented as the low-blockage option for anyone whose force floor allows it.

---

## 3. Air properties

### 3.1 Saturation vapour pressure — Magnus/Alduchov–Eskridge

For `t` in °C, result in Pa:

```text
p_sat(t) = 610.94 · exp( 17.625·t / (t + 243.04) )
```

Valid −40 °C … +50 °C, ≤0.4 % error. `DERIVED`.

### 3.2 Air density — moist ideal gas

```text
p_v = RH · p_sat(t)                        # RH as a fraction, 0–1
ρ   = (p − p_v)/(R_d·T)  +  p_v/(R_v·T)

R_d = 287.058 J·kg⁻¹·K⁻¹   (dry air)
R_v = 461.495 J·kg⁻¹·K⁻¹   (water vapour)
T   = t + 273.15
```

Worked check — 20.0 °C, 101 325 Pa, 50 % RH → `p_sat = 2333 Pa`, `p_v = 1167 Pa`,
`ρ = 1.1988 kg·m⁻³`. This value is a unit test.

Accuracy of the formula itself is ≈0.05 %, far below sensor uncertainty. `DERIVED` when a
BME280 is present; if humidity is unavailable FlowForge substitutes 50 % RH, records the
substitution, and demotes `ρ` to `ESTIMATED` (the resulting bias is <0.5 % across 0–100 % RH,
so this is a safe but *labelled* fallback).

### 3.3 Dynamic viscosity — Sutherland

```text
μ(T) = 1.716e-5 · (T/273.15)^1.5 · (273.15 + 110.4)/(T + 110.4)
```

`μ(293.15 K) = 1.813e-5 Pa·s`. Used only for Reynolds number. `DERIVED`.

---

## 4. Airspeed from the pitot-static probe

Incompressible Bernoulli (Mach ≤ 0.053 here, so compressibility correction is <0.1 % and is
deliberately omitted):

```text
v = k · sqrt( 2·Δp / ρ )
```

`k` is the **probe calibration factor**, a single dimensionless number absorbing probe
imperfection, misalignment, static-port position error, and the local blockage of the probe
itself. It is stored in a calibration record ([calibration.md](calibration.md#4-airspeed-calibration)).
Until calibrated, `k = 1.0` and is tagged `ASSUMED`; every result derived from it inherits
`ESTIMATED`.

Dynamic pressure at the specimen station:

```text
q = ½·ρ·v²  =  k²·Δp
```

Note the second form. It matters — see §6.

### 4.1 Why the low-speed limit is 4 m/s

`Δp = ½ρv²/k²`, so at ρ = 1.2:

| v (m/s) | Δp (Pa) | `Δp` uncertainty¹ | resulting `v` uncertainty |
| --- | --- | --- | --- |
| 3 | 5.4 | 0.27 Pa (5.0 %) | 2.5 % |
| 4 | 9.6 | 0.35 Pa (3.6 %) | 1.8 % |
| 5 | 15.0 | 0.49 Pa (3.3 %) | 1.6 % |
| 10 | 60.0 | 1.81 Pa (3.0 %) | 1.5 % |
| 15 | 135.0 | 4.05 Pa (3.0 %) | 1.5 % |
| 18 | 194.4 | 5.83 Pa (3.0 %) | 1.5 % |

¹ Sensirion SDP8xx-500Pa class: ±3 % of reading combined in quadrature with a ±0.2 Pa offset.

Below ~4 m/s the offset term starts to dominate and, worse, the *force* signal is also at its
weakest — the two error sources compound. FlowForge will run below 4 m/s if asked, but emits a
`LOW_SPEED_SNR` warning that lands in the summary.

---

## 5. Force measurement

### 5.1 Balance topology

V0 uses a **single-axis pendulum balance**: the specimen is carried on a sting hanging from a
low-friction pivot; a beam load cell reacts the resulting moment at a shorter radius.

```text
        ═══════ pivot (crossed-flexure or miniature bearing)
           │
           │  r_c ≈ 40 mm
           ├──────────► load cell (reacts horizontally)
           │
           │  r_s ≈ 120 mm
           │
        ┌──┴──┐
   flow │spec.│ ──►  drag
        └─────┘
```

Why this rather than mounting the load cell directly in line:

- Specimen weight is carried by the pivot, not by the sensitive axis, so a very low-capacity
  (high-resolution) load cell can be used without the dead load consuming its range.
- The lever ratio `r_s/r_c ≈ 3` *amplifies* the drag force at the cell, buying ~3× signal.
- Calibration is done by applying **known horizontal forces at the specimen station** with a
  pulley and calibrated masses. That single measurement folds the lever ratio, the pivot
  friction, and the small gravity-restoring term into one empirical slope. No geometry is ever
  measured and multiplied in software — see [calibration.md](calibration.md).

The lever ratio therefore never appears as a constant in the codebase. Only the fitted slope
`N per count` does.

### 5.2 Counts to force

```text
F_raw = (counts − zero_counts) / slope_counts_per_N
```

`slope_counts_per_N` comes from the calibration record; `zero_counts` from the most recent
tare. Both IDs are recorded in the run so the derivation is traceable.

### 5.3 Zero handling

Load-cell zero drift with temperature is the single largest source of irreproducibility at
this force scale. The protocol:

1. Tare at zero airflow immediately before the sweep → `zero_pre` at time `t_pre`.
2. Tare again at zero airflow immediately after the sweep → `zero_post` at `t_post`.
3. Apply a **linear zero interpolation** across the sweep:
   `zero(t) = zero_pre + (zero_post − zero_pre)·(t − t_pre)/(t_post − t_pre)`.
4. `|zero_post − zero_pre|` expressed in force units is the **zero-return error**. It is
   reported in the summary, contributes a Type B uncertainty of `zero_return/√3` (rectangular
   distribution), and triggers a `ZERO_DRIFT` warning above a configurable threshold.

Optionally the sweep can interleave a zero point between every speed step
(`measurement.interleave_zero: true`). This costs time and buys a much better drift model; it
is off by default in V0 and on for the validation experiment.

### 5.4 Fixture (tare-body) drag

The sting, the pivot shroud, and any exposed structure generate drag of the *same order as the
specimen's*. Concretely, a bare 4 mm sting with 60 mm exposed to the flow at 15 m/s produces
about 36 mN — larger than a 25 mm sphere's own 31 mN.

This is the dominant systematic in the whole instrument. Three mitigations, all used:

1. **Rear sting entry.** The sting approaches from downstream so most of its length sits in
   the specimen's own wake at reduced dynamic pressure.
2. **Shrouding.** A non-metric fairing surrounds the support up to a small gap near the model.
3. **Measured baseline.** A `fixture` run with no specimen (or with the specimen displaced
   out of the flow, if the mount design allows) is executed across the same speed grid, fitted
   as `F_fixture(v) = c·v^n`, and subtracted:

```text
F_specimen(v) = F_measured(v) − F_fixture(v)
```

The residual **interference** term — the mutual influence of specimen and support, which
subtraction cannot remove — is not measured in V0. It is instead carried as an explicit Type B
uncertainty of **20 % of the subtracted fixture drag**, which is deliberately pessimistic. It
is the reason `Cd` for a streamlined body is not credible in V0 (§9).

Both `F_measured` and `F_specimen` are retained in `processed/points.csv`. Nothing is
overwritten.

---

## 6. Drag coefficient

```text
Cd = 2·F / (ρ·v²·A)
```

with `F` the fixture-corrected specimen drag and `A` the user-provided reference area
(frontal area for all V0 specimens).

### 6.1 Air density cancels

Substituting `v = k√(2Δp/ρ)` gives `ρv² = 2k²Δp`, hence:

```text
Cd = F / (k² · Δp · A)
```

**Air density does not appear.** When airspeed is derived from the same pitot reading and the
same density used in the `Cd` denominator, `ρ` cancels exactly. This is not a curiosity — it
means:

- `Cd` uncertainty does **not** include density uncertainty at all;
- a broken or absent BME280 degrades reported `v` and `Re`, but not `Cd`;
- the pitot factor `k` enters `Cd` **squared**, making pitot calibration the highest-leverage
  calibration in the system after the load cell.

FlowForge computes `Cd` via the second form and treats the first as a presentation identity.

### 6.2 Reynolds number

```text
Re = ρ·v·L / μ(T)
```

`L` is the user-declared characteristic length (sphere/cylinder diameter, cube edge, body
chord). `Re` *does* depend on `ρ`, so it is `DERIVED` with a BME280 and `ESTIMATED` without.

---

## 7. Statistics over a sample window

For each test point the engine selects a window `[t_start, t_end]` on the device clock, after
stabilisation. Within that window, per channel:

1. **Despike.** Hampel filter: reject samples further than `3·1.4826·MAD` from a rolling
   median (window 21). Rejected sample indices are recorded, not deleted; the rejection count
   appears in the summary and a `HIGH_SPIKE_RATE` warning fires above 1 %.
2. **Robust centre.** Report both the arithmetic mean and the median. If they differ by more
   than the reported standard uncertainty, raise `SKEWED_DISTRIBUTION` — usually a sign of
   drift, a loose fastener, or a partially separated flow.
3. **Spread.** Sample standard deviation `s`.
4. **Effective sample size.** Consecutive samples are *not* independent: flow unsteadiness is
   correlated over ~0.1–1 s. Naively dividing by `√N` overstates precision by an order of
   magnitude, which would be exactly the kind of false precision this project exists to avoid.
   FlowForge computes the integrated autocorrelation time `τ_int` by the initial-positive-
   sequence estimator and uses

   ```text
   N_eff = N / (1 + 2·τ_int)          # τ_int in samples
   u_A   = s / sqrt(N_eff)
   ```

   Both `N` and `N_eff` are reported. Seeing `N = 800, N_eff = 47` on a report is informative
   and honest; seeing only `N = 800` is not.

The unfiltered mean is computed and stored alongside the filtered one. If the two differ by
more than `u_A`, that is surfaced as a warning rather than hidden.

---

## 8. Blockage

Closed-jet solid blockage accelerates the flow around the model, so the measured `Cd` is
biased **high**. A Maskell-type correction:

```text
Cd_corrected = Cd_measured / (1 + ε·S/C)          ε ≈ 2.5 for bluff bodies
```

At the V0 design point this is a *large* correction:

| Specimen | `S/C` | correction factor | effect on `Cd` |
| --- | --- | --- | --- |
| 25 mm sphere | 4.9 % | 1.123 | −11 % |
| 25 mm cube | 6.25 % | 1.156 | −13.5 % |
| 20 mm cube | 4.0 % | 1.100 | −9.1 % |

Policy:

- The correction is **off by default**. `Cd` as reported is the raw, uncorrected value.
- When enabled (`analysis.blockage_correction: maskell`), the corrected value is reported as a
  **separate field**, tagged `ESTIMATED`, with `ε` and `S/C` recorded next to it. The
  uncorrected value is always retained.
- `S/C > 5 %` always emits a `HIGH_BLOCKAGE` warning regardless of correction setting.
- Blockage is *nearly* common-mode when comparing specimens of similar frontal area, which is
  why the validation experiment specifies comparable frontal dimensions. Relative comparisons
  are far more trustworthy than absolute `Cd` here, and the report says so.

---

## 9. Error budget

Design-point numbers, 25 mm specimens, `ρ = 1.20`, expanded uncertainties at `k = 2` (≈95 %).

### 9.1 Expected forces

| v (m/s) | q (Pa) | sphere `Cd 0.47` | cube `Cd 1.05` | teardrop `Cd ≈0.12` |
| --- | --- | --- | --- | --- |
| 4 | 9.6 | 2.2 mN | 6.3 mN | 0.6 mN |
| 8 | 38.4 | 8.9 mN | 25.2 mN | 2.3 mN |
| 12 | 86.4 | 19.9 mN | 56.7 mN | 5.1 mN |
| 15 | 135.0 | 31.1 mN | 88.6 mN | 8.0 mN |
| 18 | 194.4 | 44.9 mN | 127.6 mN | 11.5 mN |

Sphere areas use `A = πD²/4 = 4.909e-4 m²`; cube `A = 6.25e-4 m²`.

### 9.2 Force uncertainty components

| Source | Type | Magnitude at the specimen station |
| --- | --- | --- |
| ADC + load-cell noise, after windowing and `N_eff` | A | 0.2 – 0.6 mN |
| Zero-return / thermal drift over a sweep | B | 0.5 – 1.5 mN |
| Calibration slope (mass accuracy + fit residual) | B | 1.0 % of reading |
| Non-linearity + hysteresis of the cell | B | 0.5 % of full scale |
| Pivot friction / stiction | B | 0.3 mN |
| Fixture-drag interference (20 % of subtracted baseline) | B | 2 – 7 mN at 15 m/s |

Combined, excluding fixture interference:
**`u(F) ≈ 1.0 mN ⊕ 1.2 % of reading`** (standard), i.e. **±2 mN ⊕ 2.4 %** expanded.

Including fixture interference the floor roughly triples at high speed. **This is the number
that decides what V0 can honestly claim.**

### 9.3 `Cd` uncertainty

From `Cd = F/(k²·Δp·A)`:

```text
u(Cd)/Cd = sqrt[ (u_F/F)² + (2·u_k/k)² + (u_Δp/Δp)² + (u_A/A)² ]
```

Worked, 25 mm sphere at 15 m/s, with a calibrated pitot (`u_k/k = 2 %`) and 3D-printed
dimensional tolerance ±0.2 mm (`u_A/A = 2·0.2/25 = 1.6 %`):

| term | value | contribution |
| --- | --- | --- |
| `u_F/F` | 2.6 mN / 31.1 mN | 8.3 % |
| `2·u_k/k` | | 4.0 % |
| `u_Δp/Δp` | | 3.0 % |
| `u_A/A` | | 1.6 % |
| **combined standard** | | **9.9 %** |
| **expanded, k = 2** | | **±20 %** |

So a V0 sphere result reads **`Cd = 0.47 ± 0.09`**. That overlaps the literature value at this
Reynolds number, which is the correct outcome — and it is a *useful* number, because the cube
and the sphere differ by more than a factor of two.

Uncalibrated pitot (`k` assumed 1.0, `u_k/k ≈ 6 %`) pushes this to ±26 %. Hence the pitot
calibration milestone.

---

## 10. What V0 can and cannot claim

**Can claim, with evidence:**

- Drag force scales as `v²`. Fitting `log F = log a + n·log v` should give `n = 2.00 ± 0.06`.
  A significant deviation is a *diagnostic*, not a discovery — it points at zero drift,
  fixture mismodelling, or a Reynolds effect.
- Repeatability. Two runs of the same specimen on the same day should agree within their
  combined uncertainty. This is the project's headline success criterion.
- Relative ranking of bluff bodies. Cube/sphere force ratio at fixed `v` is
  `(1.05·6.25)/(0.47·4.909) = 2.84` on the design geometry — far outside the error bars.
- Absolute `Cd` for bluff bodies to roughly ±20 %.

**Cannot claim:**

- `Cd` for streamlined bodies. At 15 m/s a teardrop's 8 mN sits near a fixture-interference
  term of similar size. FlowForge will report it with an error bar that makes this obvious,
  and will emit `SNR_MARGINAL` when `F < 5·u(F)`.
- Anything at all below 4 m/s for low-drag shapes.
- Absolute agreement with published wind-tunnel `Cd` to better than ~15 %, because turbulence
  intensity in a short open-circuit fan-driven tunnel is high (likely 2–5 %) and unmeasured in
  V0. This shifts sphere `Cd` in particular, since the sphere sits near its drag crisis
  sensitivity. **For this reason the cube — sharp-edged, fixed separation, Reynolds-insensitive
  — is the primary repeatability reference specimen, not the sphere.**
- Any turbulence, wake, or flow-field quantity. No instrumentation for it exists in V0.

---

## 11. Reporting rules

1. Round the expanded uncertainty to **two significant figures**; round the value to the same
   decimal place. `0.4712 ± 0.0937` prints as `0.471 ± 0.094`; `0.173829 N ± 0.0021 N` prints
   as `0.1738 ± 0.0021 N`.
2. Never print a result without its uncertainty and its provenance tag.
3. When `|value| < 3·u`, print `< 3σ — not resolved` next to the number rather than a
   confident-looking figure.
4. Plots carry error bars by default. A plot without error bars requires an explicit
   `--no-errorbars` and is stamped as such in the figure.
5. The summary always lists which calibration records were used, with their IDs and dates, and
   flags any older than `calibration.max_age_days`.
