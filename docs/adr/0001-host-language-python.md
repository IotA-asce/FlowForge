# ADR-0001 — Host application is Python 3.11+, managed with `uv`

**Status:** Accepted · 2026-08-07

## Context

The host application must parse configuration, orchestrate an experiment, apply calibration,
run robust statistics and autocorrelation analysis, propagate uncertainty, fit curves, generate
plots, and produce reports. It must also talk to a serial device at a few kilobytes per second
and keep a 4 Hz heartbeat alive.

The project's deliverable is *numbers with defensible error bars*, and its audience is people
who build wind tunnels in a spare room, not systems programmers.

## Decision

Python 3.11 or newer, dependency and environment management with `uv`.

Core dependencies: `numpy`, `scipy`, `pandas`, `matplotlib`, `pydantic` v2, `typer`,
`pyserial`, `PyYAML`. Development: `pytest`, `ruff`, `mypy`.

## Alternatives considered

**Rust.** Better latency guarantees, single-binary distribution, stronger types. Rejected
because the analysis layer — Theil–Sen fits, autocorrelation time, GUM propagation, publication
plots — is where the project's actual difficulty lies, and that work is several times more
expensive to write and review in Rust. The real-time argument does not apply: the firmware
already owns timing, deliberately ([ADR-0005](0005-timebase-and-synchronisation.md)).

**Go.** Good concurrency and deployment story, but a thin scientific ecosystem. Plotting and
statistics would be hand-rolled, which is exactly the code most likely to contain a silent
error in an instrument whose purpose is correctness.

**TypeScript/Node.** Strong for the eventual dashboard, weak for numerics. It would force a
second language for analysis anyway.

**C++ everywhere, sharing code with firmware.** Maximal reuse, minimal contributor pool, slow
iteration on the analysis stack. Sharing the protocol codec across languages is handled instead
by a shared golden-message corpus, which is the property that actually matters.

## Consequences

**Good**

- The analysis layer is short, readable, and reviewable — which is the layer where a bug turns
  into a wrong published number.
- Testing the whole pipeline against the simulator is cheap.
- `uv` gives a locked, reproducible environment, and a run records the resolved FlowForge
  version and git SHA.

**Bad, and accepted**

- Distribution requires a Python environment. Mitigated by `uv tool install flowforge`; a
  frozen binary is possible later if it becomes a real barrier.
- GC pauses and the GIL make host-side timing unreliable. This is *by design* irrelevant:
  nothing in the analysis path uses host time, and a pause long enough to matter trips the
  firmware heartbeat watchdog, which is the correct outcome (SR-2).
- The heartbeat must live on its own thread with no lock shared with the experiment engine, or
  a slow analysis step could cause a spurious abort. Explicitly designed for in
  [device-protocol.md §8](../device-protocol.md#8-session-lifecycle).
- A future high-rate camera pipeline (V3/V4) may need a compiled component. That is a
  self-contained addition behind an interface, not a rewrite.
