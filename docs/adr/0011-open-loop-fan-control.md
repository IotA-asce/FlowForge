# ADR-0011 — Open-loop fan duty with measured-speed reporting; no PID in V0

**Status:** Accepted · 2026-08-07

## Context

An experiment asks for 12 m/s. Something must turn that into a fan duty. The requirements allow
open-loop PWM in V0 while asking that closed-loop control remain possible later.

## Decision

Open loop, from a **measured** duty→speed map produced by the `flowforge calibrate fan-map`
characterisation:

1. Invert the map to seed a duty for the requested airspeed.
2. Stabilise.
3. Compare the measured airspeed against the request. If it is outside tolerance, apply **one**
   proportional correction and re-stabilise.
4. If it is still outside tolerance, record the achieved speed, flag `SPEED_OFF_TARGET`, and
   continue.
5. If flow cannot be established, fail with `SPEED_UNREACHABLE`.

**All analysis uses the measured airspeed, never the requested one.** A requested speed is a
label on a test point; it appears in `points.csv` as `requested_speed_mps` next to the measured
`v_mps`, and only the latter enters any calculation.

## Alternatives considered

**PID on measured airspeed.** The eventual right answer, and premature now. Tuning it requires
knowing the plant — fan lag, tunnel volume, sensor lag — which is not yet measured. Worse, a
badly tuned loop hunting around a setpoint injects flow unsteadiness during the sample window,
degrading the very measurement it was meant to improve, and it would be nearly impossible to
distinguish that degradation from genuine turbulence before the instrument is characterised.

**Fixed duty steps with no speed targeting** (sweep duty, report whatever speed results). Simpler
still, and defensible since analysis uses measured speed anyway. Rejected because comparing two
specimens is much easier when their test points sit at nearly the same speeds, and because a
requested-speed grid is what a user expects from `--min-speed 5 --max-speed 15 --step 1`.

**Closed loop on the fan tachometer rather than airspeed.** Tighter and faster, but rpm is not
the quantity of interest, and the rpm→airspeed relationship shifts with any change to the
tunnel's flow resistance — exactly the kind of hidden coupling that produces unexplained
between-session differences.

## Consequences

**Good**

- No control tuning is required before the instrument can produce data.
- Correctness is unaffected by an imperfect map: the analysis uses what was measured, so a poor
  map makes a sweep untidy, never wrong.
- The seam for a PID is a single function — `duty_for_speed(target, feedback)` — with everything
  above it unchanged.

**Bad, and accepted**

- Test points land at slightly different speeds between runs and between specimens. Comparison
  handles this by interpolating each run's fitted `F(v)` curve to common speeds and reporting
  the interpolation, flagged as such.
- Slow drift within a long sample window (fan warming, air warming) is not corrected. It shows
  up in the recorded airspeed standard deviation and in `speed_cv`, and an excessive value flags
  the point rather than silently biasing it.
- The fan map is tunnel-configuration-specific and invalidated by any change to flow resistance
  — a new screen, a blocked inlet, a different specimen size. It is stored as a dated record for
  exactly this reason.
