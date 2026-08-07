# FlowForge Technical Risks

Ranked by the product of impact and likelihood, judged against the project's actual success
criterion — *repeatable measurements with honest error bars* — not against feature completion.

Each risk states how it will be **detected**, because a risk you cannot observe is one you will
argue about instead of fixing.

| ID | Risk | Impact | Likelihood | Score |
| --- | --- | --- | --- | --- |
| [R-01](#r-01-support-drag-dominates-the-measurement) | Support/fixture drag comparable to specimen drag | High | **Certain** | 🔴 |
| [R-02](#r-02-fan-vibration-couples-into-the-balance) | Fan vibration couples into the force balance | High | High | 🔴 |
| [R-03](#r-03-load-cell-zero-drift) | Load-cell zero drift over a sweep | High | High | 🔴 |
| [R-04](#r-04-flow-quality) | Poor flow quality (turbulence, swirl, non-uniformity) | High | High | 🔴 |
| [R-05](#r-05-electrical-noise-from-fan-pwm) | Fan PWM noise coupling into the bridge amplifier | High | Medium | 🟠 |
| [R-06](#r-06-blockage) | Blockage bias at 5–6 % | Medium | Certain | 🟠 |
| [R-07](#r-07-fan-array-cannot-reach-the-speed-range) | Fan array cannot reach 18 m/s against the tunnel's pressure drop | Medium | Medium | 🟠 |
| [R-08](#r-08-pitot-signal-to-noise-at-low-speed) | Pitot SNR collapses below ~4 m/s | Medium | Certain | 🟠 |
| [R-09](#r-09-specimen-mounting-repeatability) | Specimen re-mounting is not repeatable | Medium | Medium | 🟡 |
| [R-10](#r-10-surface-finish-and-reynolds-sensitivity) | Print surface finish shifts `Cd`, especially for the sphere | Medium | Medium | 🟡 |
| [R-11](#r-11-simulator-overfitting) | The stack is tuned to the simulator and breaks on real data | Medium | Medium | 🟡 |
| [R-12](#r-12-horizontal-buoyancy) | Static-pressure gradient produces a horizontal buoyancy force | Low | High | 🟡 |
| [R-13](#r-13-host-timing-and-usb-buffering) | Host-side timing jitter corrupts the timebase | High | Low | 🟡 |
| [R-14](#r-14-component-substitution) | Chosen sensors unavailable or underperform | Low | Medium | 🟢 |
| [R-15](#r-15-scope-creep) | Scope creep past V0 before measurements are trustworthy | High | Medium | 🟠 |

---

## R-01 Support drag dominates the measurement

**The single largest technical problem in this instrument.** A bare 4 mm sting with 60 mm
exposed produces ~36 mN at 15 m/s; a 25 mm sphere produces ~31 mN. The support can contribute
*more than the specimen*.

Baseline subtraction removes the mean, but not the **interference** term — the mutual
influence between specimen wake and support, which is not the sum of the parts measured
separately.

- **Mitigation:** rear-sting entry so the support sits in the model's wake; a non-metric
  shroud around the support with a small gap near the model; the thinnest sting that is stiff
  enough; mandatory fixture-baseline runs.
- **Residual, carried explicitly:** 20 % of the subtracted fixture drag as a Type B
  uncertainty ([measurement-model.md §5.4](measurement-model.md#54-fixture-tare-body-drag)).
- **Detection:** run the fixture baseline with two different sting diameters. If the *specimen*
  drag inferred from each differs by more than the stated uncertainty, the interference model
  is wrong and the uncertainty must grow.
- **Consequence, accepted:** streamlined-body `Cd` is not credible in V0.

## R-02 Fan vibration couples into the balance

A pendulum balance is a lightly damped second-order system. Four fans running at 1500–3000 rpm
with 7–9 blades put energy at 175–450 Hz (blade-pass) plus a strong once-per-rev component. If
the balance's natural frequency lands near either, force noise is amplified by the quality
factor and the measurement floor collapses. Worse, the amplification varies with fan duty, so
it looks like a speed-dependent force — i.e. exactly like drag.

- **Mitigation:** soft-mount the fans on elastomer isolators; mechanically decouple the balance
  from the tunnel shell (separate rigid stand, tunnel wall sealed to the sting with a
  non-contacting labyrinth or a slack membrane); design the balance's first natural frequency
  well below the excitation and rely on the ADC's inherent low-pass.
- **Detection, mandatory before believing any data:** a **tap test** on the assembled balance
  (strike it, record the ringdown at the full sample rate, take an FFT) to find `f_n` and
  damping; then a **fan-only test** with the test section blocked so there is no flow past the
  specimen, sweeping duty across the whole range and recording apparent force. Any duty-
  dependent apparent force is contamination, and it must be below the force uncertainty before
  the instrument is trusted. This test is a milestone gate in [v0-plan.md](v0-plan.md).
- **Note:** the sigma-delta ADC's SINC filter provides genuine anti-alias filtering, so
  high-frequency vibration is attenuated rather than folded down to DC. This is a specific
  reason to prefer NAU7802/HX711 over an SAR ADC here.

## R-03 Load-cell zero drift

Thermal drift of the bridge zero is the dominant irreproducibility at the millinewton scale.
Fans heat the air; the air heats the balance; the zero walks over exactly the timescale of a
sweep.

- **Mitigation:** 15-minute warm-up before calibration and before runs; pre- and post-sweep
  tares with linear interpolation; `interleave_zero` for anything precision-critical; keep the
  load cell out of the heated airstream.
- **Detection:** the zero-return figure is computed and reported on every run, and
  `ZERO_DRIFT` fires above threshold. A sweep run ascending and then descending should
  retrace; hysteresis in that loop is drift, not physics.

## R-04 Flow quality

A short open-circuit fan-driven tunnel has high turbulence intensity — plausibly 2–5 % even
with honeycomb and screens — plus residual swirl and a non-uniform velocity profile. This is
the main reason absolute `Cd` will not match published values, especially for a sphere, whose
drag is sensitive to turbulence near the drag crisis.

- **Mitigation:** fans upstream blowing into a settling chamber (not pulling downstream of the
  test section); honeycomb with cell length ≥ 8× cell diameter; two or three fine screens;
  4 : 1 contraction, which reduces axial turbulence roughly with the contraction ratio.
- **Detection:** a velocity traverse across the test section (5- or 9-point) to quantify
  uniformity, recorded in the tunnel characterisation. Turbulence intensity itself is not
  measurable in V0 without a hot-wire.
- **Consequence, accepted and stated in every report:** absolute `Cd` is claimed to ±15–20 %.
  Relative comparison and repeatability are the deliverables. **The cube, not the sphere, is
  the primary reference specimen**, because a sharp-edged body has fixed separation points and
  is largely insensitive to both Reynolds number and turbulence.

## R-05 Electrical noise from fan PWM

The load cell produces microvolts. The fan array switches amps at 25 kHz a few centimetres
away. Coupling produces an apparent force that scales with duty — again, indistinguishable
from drag by inspection.

- **Mitigation:** ADC board mounted at the load cell, not at the MCU; shielded twisted-pair
  from the bridge with the shield grounded at one end only; fan power wiring physically
  separated and twisted; separate ground return for the analogue section, star-grounded;
  25 kHz PWM (above audio, and far from the ADC's output rate) with the ADC's SINC filter
  attenuating it.
- **Detection:** the same fan-only, flow-blocked duty sweep as R-02. That one test separates
  vibration from electrical coupling if repeated with the fan mechanically decoupled but
  electrically connected.

## R-06 Blockage

4.9–6.25 % blockage at the design point biases `Cd` high by 11–14 %. Fully characterised in
[measurement-model.md §8](measurement-model.md#8-blockage); the correction is available,
off by default, always reported separately, and always accompanied by the uncorrected value.
Largely common-mode across specimens of similar frontal area, which protects the comparison
even where it degrades the absolute number.

## R-07 Fan array cannot reach the speed range

18 m/s through 0.01 m² is 0.18 m³/s ≈ 380 CFM, and the tunnel's honeycomb, screens, and
contraction impose meaningful static pressure. Fans are rated at *free air*; delivered flow on
the system curve is substantially lower.

- **Mitigation:** specify **high-static-pressure** fans (the ones rated in mmH₂O, not the
  quiet-airflow ones), size the array with ≥50 % margin, and keep the settling chamber large so
  the screens see low velocity — pressure drop across a screen goes as velocity squared, so a
  4 : 1 contraction cuts the screen loss roughly sixteenfold.
- **Detection:** measure the achieved top speed during the fan-map characterisation, before any
  aerodynamic work. If it falls short, the honest response is to narrow the declared speed
  range, not to run the fans past their rating.
- **Fallback:** reduce the top of the range to 15 m/s. Nothing in the analysis depends on the
  specific range.

## R-08 Pitot signal-to-noise at low speed

At 3 m/s, `Δp` is 5.4 Pa and a ±0.2 Pa offset is 4 % of it. Compounded by the force signal also
being at its weakest, low-speed points are the least trustworthy in every sweep. Handled by the
declared 4 m/s floor, a `LOW_SPEED_SNR` warning, and honest error bars rather than by
pretending otherwise.

## R-09 Specimen mounting repeatability

Remounting a specimen at a slightly different angle or axial position changes its drag. For a
sphere this is negligible; for a teardrop, a few degrees of incidence is a large relative
change.

- **Mitigation:** keyed/pinned mount so orientation is mechanically determined, not eyeballed;
  a printed alignment fixture; specimen `revision` recorded per run.
- **Detection:** `flowforge verify repeatability` with a *deliberate remount between the two
  runs*. Mount-to-mount repeatability is a different and more useful number than
  back-to-back repeatability, and both belong in the validation report.

## R-10 Surface finish and Reynolds sensitivity

FDM layer lines are roughness elements. On a sphere at Re ~2×10⁴ they can trip the boundary
layer and shift `Cd` noticeably; on a sharp-edged cube they barely matter.

- **Mitigation:** specify print orientation, layer height, and post-processing in
  `specimen.json`, and keep them constant across a comparison set.
- **Detection:** print one specimen twice with different layer heights and compare. If they
  differ beyond uncertainty, surface finish is a controlled variable and must be reported.

## R-11 Simulator overfitting

The whole vertical slice is built against a simulator we also wrote. The failure mode is a
stack that works beautifully on synthetic data and falls apart on the first real sweep.

- **Mitigation:** the simulator is deliberately *unkind* — 1/f drift, correlated flow
  unsteadiness, quantisation, offset drift, dropouts, and injectable faults are all on by
  default in integration tests. The analysis must never assume a noise model the simulator
  happens to generate; robust statistics and `N_eff` are used precisely because they do not.
- **Detection:** the first real dataset is treated as a discovery exercise with an explicit
  milestone (M7 in [v0-plan.md](v0-plan.md)) for reconciling simulator behaviour with measured
  behaviour, and the simulator's parameters are then re-fitted from real data.

## R-12 Horizontal buoyancy

A static-pressure gradient along the test section (from boundary-layer growth on the walls)
exerts a net streamwise force on the model even with zero drag. Classical wind-tunnel practice
corrects for it.

- **Mitigation:** a slightly diverging test section compensates boundary-layer growth; in V0
  the simpler answer is that the fixture baseline absorbs most of the fixture's share.
- **Detection:** measure static pressure at two stations along the test section. If the
  gradient is significant, the correction is documented but the effect is small at this scale
  and short length — hence the low impact rating.

## R-13 Host timing and USB buffering

Python scheduling jitter, OS serial buffering, and USB frame timing are all tens of
milliseconds. If host receive time were the timebase, the measurement would be corrupted.

- **Mitigation:** this is exactly why the firmware timestamps every sample and why the device
  clock is the measurement timebase
  ([ADR-0005](adr/0005-timebase-and-synchronisation.md)). Host time is recorded, mapped, and
  never used in analysis.
- **Detection:** the clock-sync residual MAD is recorded per run. A jump indicates a serial
  buffering problem; the analysis is unaffected either way.

## R-14 Component substitution

The NAU7802, SDP810, and BME280 are all substitutable. The HAL layer means a swap is one
firmware file plus a `hello` channel descriptor. The HX711 is the documented budget fallback
for the load-cell ADC at the cost of resolution and a fixed 10/80 SPS choice.

## R-15 Scope creep

The most likely way this project fails is not a measurement error — it is building a dashboard,
a PIV pipeline, or a CFD importer before the drag bench produces repeatable numbers.

- **Mitigation:** the V0 acceptance criteria are written down and are the only definition of
  done. [v0-plan.md](v0-plan.md) sequences milestones so that every one is independently
  verifiable, and the non-goals list in the requirements is treated as binding.
- **Detection:** if a milestone's acceptance test cannot be stated as a measurement, it is not
  a V0 milestone.
