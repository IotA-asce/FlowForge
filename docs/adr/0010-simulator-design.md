# ADR-0010 — Two-level simulator: in-process instrument and wire-level transport

**Status:** Accepted · 2026-08-07

## Context

The requirements make a mock wind tunnel mandatory, so that the experiment engine, analysis,
and CI can run with no hardware. The entire first vertical slice (M0–M7) is built against it.

That creates a specific danger: a stack that works perfectly against a simulator we also wrote,
and falls apart on the first real sweep — [R-11](../technical-risks.md#r-11-simulator-overfitting).

## Decision

**Two levels, sharing one plant model.**

*Level 1 — `SimInstrument`.* Satisfies the device protocols in-process. Advances a **virtual
clock**, so a 600 s sweep runs in milliseconds. Used by most unit tests and all
experiment-engine tests.

*Level 2 — `SimTransport`.* Implements the byte-level `Transport` interface and speaks the real
NDJSON protocol, driven by the same plant model. Used by codec tests and by at least one
end-to-end integration test, so the wire format, framing, sequence handling, ack/timeout logic,
and clock-offset estimator are all exercised in CI without hardware.

The plant model — fan first-order lag, duty→speed map with a stall threshold, Ornstein–Uhlenbeck
turbulence, drag from a configurable ground-truth `Cd` plus configurable fixture drag, load cell
modelled by *inverting* a calibration record with white noise plus 1/f drift plus quantisation,
pitot with offset drift, slow environmental variation — is fully seeded. Same seed, byte-identical
output.

**The simulator is deliberately unkind.** Drift, correlated noise, quantisation, dropouts, and
injectable faults are on by default in integration tests, not opt-in extras.

Simulated runs are unmistakable: `metadata.json` records `"backend": "sim"` with the plant
parameters and seed, and the report header says so.

## Alternatives considered

**Only an in-process mock.** Fast and simple, and it would leave the codec, framing, retry, and
clock-sync logic — some of the most failure-prone code in the project — untested until hardware
arrives, which is exactly when debugging is most expensive.

**Only a wire-level simulator.** Faithful, but every engine test would pay serialisation cost
and, worse, could not use a virtual clock without simulating time through the transport. Sweep
tests would take minutes.

**A separate process pretending to be a serial device (pty/socat).** Closer to reality, at the
cost of process management, flaky CI, and platform-specific plumbing. `SimTransport` gets the
same coverage inside the test process.

**A CFD-derived plant model.** Would make the simulator's `Cd` "realistic". Pointless: the
simulator exists to test the *software*, and a configurable ground-truth `Cd` is strictly better
for that because the correct answer is known exactly.

## Consequences

**Good**

- CI covers everything from wire bytes to the final report with no hardware, and fast.
- The headline acceptance test — recover a configured ground-truth `Cd` within the stated
  expanded uncertainty, across 200 seeds, with a coverage rate between 90 % and 99 % — validates
  the *uncertainty model*, not just the mean. Error bars that are too narrow and error bars that
  are too wide both fail.
- Fault injection makes failure paths ordinary tests rather than manual experiments.

**Bad, and accepted**

- Two implementations to keep in step. Bounded by both being thin wrappers over one plant model.
- The plant model is a guess until real data exists. M8c and M9 explicitly re-fit its noise and
  drift parameters from measurements, and the error budget is updated with measured values at
  the same time.
- A simulator this detailed invites being treated as a product. It is test infrastructure: it is
  not documented for end users, and it is not a supported way to "run an experiment".
