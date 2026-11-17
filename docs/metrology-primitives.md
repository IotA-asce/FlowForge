# Initial metrology primitives

The first M0 slice is a dependency-free Python library, not a working instrument.
No device, serial, fan or model interface is present. The accepted numeric examples
are test fixtures, not measurements or evidence of calibrated accuracy.

`Quantity(value, u, unit, provenance, coverage_factor=1, ...)` is immutable. `u`
is standard uncertainty in the same unit as value; a positive integer coverage
factor expands only the displayed interval. Units are reporting labels, not a
checked conversion system. Non-finite values/uncertainties, negative uncertainty,
invalid coverage factors and undocumented provenance tags are rejected.

The central string formatter rounds expanded uncertainty to two significant
figures, aligns the value's decimal place, and always includes unit/provenance.
It handles rounding carry (0.0996 becomes 0.10), explicitly reports `u=None` as
"uncertainty not established", and adds `< 3σ — not resolved` when magnitude is
below three **standard** uncertainties. A coverage factor other than 1 is shown.
This is a reporting convention, not a hypothesis test or confidence guarantee.
Zero uncertainty remains an explicit caller-supplied claim, not an inferred one.

`Quantity.derived(..., inputs={"name": quantity}, formula="...")` records named
inputs and computes the origin tag. ASSUMED or ESTIMATED sources demote a result
to ESTIMATED; an empirical model must explicitly request `estimated=True` even
when its inputs are measured. USER_PROVIDED is an origin label, not an implicit
claim that a sensor measured it or an automatic conversion to ASSUMED. Empty
input lists cannot create a derived result. All five source tags and their pairs
are tested against this policy.

Numerical uncertainty propagation is deliberately explicit: the computed
constructor requires a supplied `u` (possibly unknown) and formula. It does not
invent a GUM equation, correlations or omitted uncertainty terms. Those equations
belong to the later scientific functions and must be independently validated.

## Current checks and remaining work

Run `uv run --locked pytest`, `uv run --locked mypy`, and
`uv run --locked ruff check .`; format Python source/tests with
`uv run --locked ruff format --check src tests`. Existing design-document
code examples are not reformatted as part of this foundation. Core syntax/API requires Python 3.11+. Dev dependency
versions are recorded in uv.lock; build backend requirements are resolved at
build time and are not claimed to be separately frozen by that lock.

TODO for complete M0: units/errors/logging helpers, import-direction lint and CI.
TODO for later milestones: simulator, acquisition/storage/calibration, scientific
propagation, run-summary warnings, experiment engine, CLI, firmware and hardware
validation. No M0 completion or instrument-readiness claim is made by this slice.
