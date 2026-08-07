# ADR-0007 — Device abstraction via structural `Protocol`s, no plugin framework

**Status:** Accepted · 2026-08-07

## Context

FlowForge must run identically against real hardware and against a simulator, and must tolerate
sensor substitution (NAU7802 ↔ HX711, SDP810 ↔ SDP31) without changes above the device layer.
The requirements ask for explicit device interfaces and forbid scattering serial commands
through the application.

## Decision

Interfaces are `typing.Protocol` classes in `devices/interfaces.py`: `FanController`,
`ForceSensor`, `AirspeedSensor`, `EnvironmentSensor`, `AngleController`, and the composite
`Instrument`. A backend is any class that structurally satisfies the protocol. There is no base
class to inherit and no entry-point plugin system.

Backend selection is a dictionary in `devices/registry.py` keyed by a config string
(`"serial"`, `"sim"`). Adding a backend is a new module plus one dictionary entry.

Sensor reads are **pull-from-buffer**: the device streams continuously into an acquisition ring
buffer, and `latest()` and the windowing API read from it. No sensor method blocks on hardware.

`AngleController` is declared now and returns `None` from the V0 registry.

## Alternatives considered

**Abstract base classes.** Conventional and would work. `Protocol` is preferred because the
simulator and any test double are then genuinely independent of the production hierarchy —
there is no way to accidentally inherit real behaviour into a fake — and because `mypy` checks
conformance structurally without an inheritance ceremony.

**Entry-point plugin system.** Would allow third-party device packages. Nobody is writing one.
It costs a discovery mechanism, versioning of the plugin API, and error handling for broken
plugins, in exchange for a feature with no user.

**One monolithic `Device` class with per-hardware `if` branches.** Exactly what the requirements
prohibit, and it makes the simulator a special case inside production code rather than a peer
implementation.

**Blocking `read()` per sensor.** The obvious API, and wrong for this instrument: it would make
the host's call timing part of the measurement, contradicting
[ADR-0005](0005-timebase-and-synchronisation.md), and it cannot express a channel that samples
faster than the caller polls.

## Consequences

**Good**

- `SimInstrument` and `SerialInstrument` are peers; the experiment engine cannot tell them
  apart, which is what makes the whole engine testable without hardware.
- A sensor swap is one HAL file in firmware plus a channel descriptor — no host change.
- `mypy` catches interface drift at check time.

**Bad, and accepted**

- Structural typing means a backend can satisfy the protocol while behaving wrongly. Mitigated
  by a shared **conformance test suite** that every backend must pass, including the simulator
  and the serial backend against `SimTransport`.
- `Protocol` gives no shared implementation, so small helpers may be duplicated across backends.
  Acceptable at two backends; a mixin is the answer if it becomes three.
- Pull-from-buffer means callers must handle `None` (no sample yet) and must reason about buffer
  staleness. Made explicit by returning `None` rather than a stale value, and by the `STALE`
  status bit in telemetry.
