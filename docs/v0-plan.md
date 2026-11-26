# FlowForge V0 Implementation Plan

**V0 = automated drag bench.** One force axis, one specimen orientation, automatic airspeed
sweeps, honest error bars, reproducible run directories.

The plan is ordered so that **everything up to and including M7 runs without any hardware**.
The instrument is proven in software first, then one sensor is connected at a time.

Rule for every milestone: *if the acceptance test cannot be stated as an assertion a machine can
check, it is not a milestone.*

---

## Milestone map

```text
 software-only, no hardware required                        hardware
┌───────────────────────────────────────────────────┐   ┌──────────────────────┐
 M0 ─► M1 ─► M2 ─► M3 ─► M4 ─► M5 ═► M6 ─► M7 ────────► M8a ─► M8b ─► M8c ─► M8d/e ─► M9 ─► M10
 skel   sim   acq   cal   eng  SLICE  cli  proto        fw     fan    load    flow    tunnel  validate
                                 ▲                      core   +HIL   cell    +env    char.
                                 │
                    first vertical slice complete
```

---

## M0 — Skeleton and primitives

**Build:** `pyproject.toml` (uv, hatchling), package layout per
[architecture.md §4.3](architecture.md#43-repository-layout), ruff + mypy (strict on
`aero`, `signal`, `calibration`) + pytest, GitHub Actions CI. Leaf modules: `units`,
`provenance`, `quantity`, `errors`, structured logging setup.

**Key content:** the `Quantity` type — `value`, `u`, `unit`, `provenance`, optional
`coverage_factor`/`formula`/`method`/`inputs` — plus the provenance propagation rule (a
`DERIVED` computation consuming an `ASSUMED` input yields `ESTIMATED`) and the significant-
figure formatter.

**Done when:** `uv run pytest` and `uv run mypy` are green in CI; `Quantity(0.4712, u=0.0937)`
formats as `0.471 ± 0.094`; provenance propagation is unit-tested across all five tags.

**Progress — 17 November 2026:** first M0 subset implemented and locally verified:
installable Python 3.11+ package, Quantity/provenance leaves and central formatter.
The documented numeric examples, all five tags, mixed-origin demotion, rounding
carry, coverage and unresolved/unknown warnings have executable tests. **M0 is
not complete:** units/errors/logging, import-direction guard and CI remain TODO.
No simulator, experiment engine, device path or CLI has been implemented yet.

**Progress — 18 November 2026:** static import-direction enforcement and a locked
Python 3.11/3.13 Ubuntu CI workflow are implemented. The guard checks all package
source, absolute/relative imports and re-exports, unclassified module roots, and
indirect device dependencies from scientific layers. See
[software-validation.md](software-validation.md) for limits and commands.
Units/errors/logging helpers remain TODO, so **M0 is still partial**.

**Progress — 20 November 2026:** the units leaf now provides explicit mm/metres,
g/kg, percent/fraction and absolute Celsius/kelvin edge conversions, with finite
input/output and temperature-domain guards. See [units.md](units.md). Quantity
units remain labels; numerical uncertainty propagation is not implemented by
these helpers. **M0 remains partial:** errors/logging are TODO.

**Progress — 23 November 2026:** errors and explicit structured logging leaves
are implemented; see [errors-logging.md](errors-logging.md). The caller owns the
human INFO and JSON DEBUG streams; no import-time/global logging setup or run
storage lifecycle is introduced. All M0 primitives, layering checks and CI are now
implemented, with 175 tests covering the foundation. This closes the M0 implementation
scope; M1 onward remain separate, including the simulator and instrument CLI.

## M1 — Simulator plant and device protocols

**Build:** `devices/interfaces.py` (the `Protocol` definitions), `devices/sim/` with the plant
model from [architecture.md §6](architecture.md#6-the-simulator), and a virtual clock.

**Key content:** fan first-order lag; duty→speed map with a stall threshold; Ornstein–Uhlenbeck
turbulence; drag from a configurable ground-truth `Cd` plus a configurable fixture drag; load
cell modelled as force → counts through the *inverse* of a calibration record, with white
noise, 1/f drift, and quantisation; pitot with offset drift; slow environmental variation;
injectable faults.

**Done when:** the same seed produces byte-identical sample streams; a 600 s simulated sweep
completes in under a second of wall time; every declared fault type can be injected and is
observable at the device interface.

**Progress — 25 November 2026:** `devices/sim/clock.py` provides a virtual device
clock with exact integer microsecond timestamps and explicit nonnegative advances.
It never waits on wall time. The plant model, device protocols, injected faults,
sample replay, and full simulated sweep remain open.

**Progress — 26 November 2026:** `devices/sim/fan.py` implements the constant-duty
part of the fan plant. It computes the affine target above stall and advances
airspeed with the exact first-order response for the elapsed interval. Slope
and stall duty are caller-supplied model parameters. Sensor models, noise,
faults and sweep integration remain open.

## M2 — Acquisition and storage

**Build:** ring buffers, per-channel sequence/dropout accounting, time-window selection,
`storage/` writers for `raw/samples.csv`, `raw/events.jsonl`, `raw/phases.csv`,
`metadata.json`, `manifest.json`, and the readers for all of them.

**Done when:** a canned 60 s acquisition against `SimInstrument` produces a run directory that
`flowforge verify` hash-checks clean; injected dropouts appear in the summary with the right
counts; `raw/` is read-only after close; a round-trip write→read→write of every file is
byte-stable.

## M3 — Calibration

**Build:** calibration record schema, store, fitting (weighted OLS with covariance-derived
slope uncertainty), acceptance criteria, tare including pre/post interpolation and zero-return,
and the counts→SI application path.

**Done when:** a synthetic calibration with a known slope is recovered within its own reported
uncertainty; each acceptance criterion in
[calibration.md §2.4](calibration.md#24-acceptance-criteria) is proven to reject a crafted bad
dataset; local-gravity computation matches a reference value; a run referencing a missing or
expired record fails or warns exactly as specified.

## M4 — Experiment engine

**Build:** pydantic config schema for `request.yaml`/`run.yaml`, the state machine, the sweep
executor, stabilisation (fixed interval plus the optional statistical check), the abort path,
and the failure-reason enum.

**Done when:** a full sweep runs against `SimInstrument`; a property test asserts `ABORTING` is
reachable from every state and that its first action is `fan.stop()`; every failure reason can
be provoked and produces a valid, closable run directory; an invalid config fails in
`VALIDATING` before the device is touched; unknown config keys are rejected.

## M5 — First vertical slice ⭐

**Build:** `signal/` (Hampel despike, robust statistics, integrated autocorrelation time and
`N_eff`), `aero/` (density, viscosity, pitot, `q`, `Cd` via the `k²Δp` form, `Re`, blockage,
GUM uncertainty propagation), `analysis/` (per-point aggregation, power-law fit, weighted `Cd`
aggregate), `report/` (markdown report + the four standard plots).

**This is the milestone the requirements name as the proof of concept.**

**Done when — all of these:**

1. A fully simulated sweep sets airflow, stabilises, samples, persists raw data, computes
   results, and writes a valid run directory with a report. No hardware, no manual steps.
2. **Ground truth recovery:** with the simulator configured at `Cd = 0.47`, the reported
   `Cd` bracket includes 0.47 — and, run across 200 seeds, it does so between 90 % and 99 % of
   the time. Too-narrow *and* too-wide error bars both fail. This tests the uncertainty model,
   not just the mean.
3. **Scaling:** the fitted power-law exponent is `2.00 ± 0.06`.
4. **Density cancellation:** perturbing the simulator's ambient pressure by 5 % changes
   reported `v` and `Re` but leaves `Cd` unchanged to within floating-point tolerance —
   a direct test of [measurement-model.md §6.1](measurement-model.md#61-air-density-cancels).
5. **Fixture subtraction:** a simulated fixture-drag component is recovered by a baseline run
   and removed to within its stated uncertainty.
6. **Reanalysis:** `flowforge analyze` on the finished directory reproduces `summary.json`
   bit-for-bit. Swapping in a calibration record with a 10 % different slope changes the
   reported force by exactly 10 %.
7. **No bare floats:** a test asserts every numeric leaf in `summary.json` is a `Quantity`
   object with a provenance tag.

## M6 — CLI and comparison

**Build:** `flowforge devices | status | calibrate | tare | run | experiments | analyze |
compare | verify`, progress output, and the comparison compatibility checks.

**Done when:** the CLI transcript matches the requirement's example shape; `compare` produces
the normalised drag ratio table; comparison **warns** on differing calibration records,
substantially different environmental conditions, incompatible reference areas, missing
metadata, and mixed sim/hardware backends — each proven by a test with a crafted run pair;
`--json` output is available on every read-only command.

## M7 — Wire protocol and transports

**Build:** the NDJSON codec, `SimTransport` (the plant model behind the real wire format), the
`pyserial` transport, connection lifecycle, ack/timeout/retry, heartbeat thread, and the
clock-sync estimator.

**Done when:** golden-file codec tests round-trip a corpus of literal message strings;
malformed lines, oversize lines, and unknown message types are counted and survived rather
than fatal; a full experiment runs end to end over `SimTransport` with injected dropouts,
duplicated `req` ids, and a simulated disconnect; the clock-sync estimator recovers an injected
skew of 30 ppm; the heartbeat thread keeps running while the main thread is artificially
stalled.

**At the end of M7 the entire host stack is complete and tested. No hardware has been touched.**

---

## Hardware integration — one thing at a time

## M8a — Firmware core (no board needed)

PlatformIO project; `proto/` and `safety/` written as portable C++ with no hardware includes;
device state machine; command dispatch.

**Done when:** `pio test -e native` passes in CI; SR-2, SR-5, SR-6, SR-7, SR-12 from
[safety.md §2](safety.md#2-software-safety-requirements) are proven by native unit tests; the
firmware codec passes the *same* golden message corpus as the host.

## M8b — Fan control on real hardware

ESP32-S3 board, LEDC PWM, tachometer capture, heartbeat watchdog, E-stop sense line.

**Done when — hardware-in-the-loop tests, run manually and recorded:** SR-1 (power cycle while
commanding duty), SR-2 (kill the host process), SR-3 (unplug USB), SR-4 (replug — fan must stay
off), SR-11 (block an inlet), and the E-stop test. Duty ramp verified on a scope. **No sensor
work begins until every one of these passes.**

## M8c — Load cell

NAU7802 driver, DRDY-driven sampling, streaming to the host, bench calibration with masses.

**Done when:** achieved sample rate is within 1 % of nominal over 10 minutes with zero dropped
batches; a calibration meets all acceptance criteria; a check mass is recovered within stated
uncertainty; measured single-sample noise is recorded and compared against the 0.02 % FS
assumption in the error budget — and the error budget is **updated with the measured value**.

## M8d — Differential pressure · M8e — Environment

SDP810 and BME280 drivers, zero-offset handling, self-heating check.

**Done when:** Δp zero offset is stable across a session; the BME280 reads plausible ambient
values and its self-heating offset is measured and recorded.

## M9 — Tunnel build and characterisation

Physical build per [BOM](../hardware/BOM.md), then characterisation *before* any aerodynamic
claim:

1. **Fan map:** duty→speed, ascending and descending, hysteresis recorded. Establishes the
   real achievable speed range (R-07).
2. **Velocity traverse:** 9-point across the test section; uniformity recorded.
3. **Tap test:** balance natural frequency and damping from a ringdown FFT (R-02).
4. **Fan-only noise test — the gate:** test section blocked so there is no flow over the
   specimen; sweep fan duty across the full range; record apparent force.

**Gate:** the duty-dependent apparent force from vibration and electrical coupling must be
**below the force uncertainty** from the error budget. If it is not, M9 does not pass, and the
fix is mechanical or electrical (R-02, R-05) — not a software filter. Filtering out a
duty-dependent artefact would remove real drag along with it.

## M10 — First validation experiment

Three specimens — 25 mm cube, 25 mm sphere, streamlined teardrop — comparable frontal
dimensions, printed with documented and identical process parameters.

Protocol:

- Fixture-baseline sweep first.
- Each specimen swept 4 → 18 m/s in 2 m/s steps, `interleave_zero: true`.
- Each specimen run **twice back to back** (measurement repeatability) and **once more after a
  deliberate remount** (mounting repeatability, R-09).
- Full methodology, raw data, and results committed to `examples/validation-2026/`.

**Done when:**

1. Repeat runs of the same specimen agree within combined uncertainty at every point above the
   SNR threshold.
2. The power-law exponent is `2.00 ± 0.10` for the cube and the sphere.
3. Cube and sphere drag are separated by far more than their error bars; the measured force
   ratio is compared against the geometric expectation of ≈2.8 and any discrepancy is
   *discussed*, not hidden.
4. The teardrop is reported with an error bar that makes its marginal SNR obvious, and
   `SNR_MARGINAL` fires where it should.
5. `docs/experiments/validation-2026.md` publishes the complete methodology, including what did
   **not** work.

---

## Mapping to the V0 acceptance criteria

| Requirement area | Satisfied by |
| --- | --- |
| Fan controlled programmatically | M8b |
| Airspeed measured | M8d |
| Drag force measured | M8c |
| Environmental conditions recorded | M8e |
| Fails to a safe fan-off state | M8a, M8b (SR-1…SR-14) |
| Load-cell calibration persisted | M3, M8c |
| Sensors tared | M3 |
| Calibration traceable per experiment | M2 (`calibration.json` snapshot), M3 |
| Sweep without manual speed changes | M4 |
| Automatic stabilise + sample per point | M4 |
| Raw samples saved | M2 |
| Experiment configuration saved | M2, M4 |
| Reproducible / reanalysable | M2, M5 (acceptance 6) |
| Mean force per point, noise reported | M5 |
| Drag-vs-speed curves | M5 |
| `Cd` estimated when metadata exists | M5 |
| Experiments compared | M6 |
| Engine runs entirely simulated | M1, M4, M5 |
| CI needs no hardware | M0…M7, M8a |
| BOM, wiring, calibration, test-section docs | M9 + `hardware/` |
| Benchmark experiment documented | M10 |

---

## Sequencing rules

1. **No hardware before M7.** The temptation to plug in a load cell early is the main way this
   project acquires an untestable stack.
2. **No sensors before M8b passes.** Safety first is not a slogan here; a fan that cannot be
   stopped reliably makes every subsequent test unsafe to repeat.
3. **No aerodynamic claim before M9's gate.** Duty-dependent artefacts masquerade as drag.
4. **The error budget is updated with measured values as they arrive** (M8c, M9). The numbers
   in [measurement-model.md §9](measurement-model.md#9-error-budget) are design estimates and
   are labelled as such until replaced.
5. **Nothing from V1–V6 is implemented in V0**, including the dashboard. The seams listed in
   [architecture.md §13](architecture.md#13-explicit-v0-boundaries) are free; anything that is
   not free waits.
