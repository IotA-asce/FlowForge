# ADR-0012 — Uncertainty and provenance are types, not conventions

**Status:** Accepted · 2026-08-07

## Context

The requirements are blunt about this: `Drag: 0.17382941 N` is meaningless when the sensor
uncertainty is ±0.02 N, and FlowForge must distinguish measured from derived from estimated from
assumed.

Both requirements are easy to satisfy in a report template and easy to violate everywhere else.
A parallel `dict` of uncertainties, or a naming convention like `force_u`, works exactly until
someone adds a code path that forgets it — and that path is invisible, because a bare float
prints beautifully.

## Decision

A single type carries every reportable quantity:

```python
@dataclass(frozen=True)
class Quantity:
    value: float
    u: float | None                 # standard uncertainty, same unit
    unit: str
    provenance: Provenance          # MEASURED | DERIVED | ESTIMATED | ASSUMED | USER_PROVIDED
    coverage_factor: int = 1
    formula: str | None = None      # doc reference, e.g. "measurement-model.md §3.2"
    method: str | None = None
    inputs: tuple[str, ...] = ()
```

Enforced properties:

1. **Provenance propagation is automatic.** A `DERIVED` computation consuming any `ASSUMED`
   input yields `ESTIMATED`. Implemented once, in `flowforge.provenance`, and unit-tested across
   all five tags.
2. **Uncertainty propagation is explicit.** `aero` functions take and return `Quantity`, and
   combine uncertainties by the GUM first-order rule. Where a term is deliberately neglected,
   the omission is named in `formula` or `method` — not silently dropped.
3. **Formatting is centralised.** One formatter rounds the expanded uncertainty to two
   significant figures and the value to the same decimal place. There is no other way to render
   a result.
4. **`u=None` is legal but loud.** It means "uncertainty not established", prints as such, and
   causes a warning in the summary. It never prints as a clean number.
5. **A test asserts every numeric leaf in `summary.json` is a `Quantity`**, so a bare float
   cannot reach a result file.

## Alternatives considered

**`uncertainties` package** (automatic linear error propagation via operator overloading). Very
attractive: correlation tracking comes free and the arithmetic reads naturally. Rejected for V0
because it does not carry units or provenance, it hides where uncertainty enters — the thing
that most needs to be readable in an instrument's source — and its NumPy interop adds friction
in the array-heavy signal layer. Worth revisiting if correlated inputs become common; the
`Quantity` boundary makes swapping the internals contained.

**`pint` for units.** Solves unit safety properly. Rejected as one dependency too many for a
codebase that is SI-internal by fiat, where unit errors are prevented instead by naming
convention (`reference_area_m2`) and conversion only at the I/O edges. `Quantity.unit` is a
label for reporting, not a checked type — a known, accepted gap.

**Convention only** (parallel `_u` fields, a report template that does the rounding). Cheapest,
and it fails in the one way that matters: silently, in the direction of overclaiming.

## Consequences

**Good**

- False precision is structurally hard to emit rather than merely discouraged.
- `summary.json` is self-describing: every number states its unit, its uncertainty, its
  provenance, and often the document section defining its formula.
- The uncertainty model is *testable*, and is tested — M5's coverage test asserts that reported
  intervals contain the simulator's ground truth at the expected rate.

**Bad, and accepted**

- Verbosity. Arithmetic on `Quantity` is wordier than on floats, and the signal layer converts
  to plain NumPy arrays for bulk work, re-wrapping only at aggregation boundaries. The boundary
  is where mistakes can hide, so it is explicitly tested.
- No correlation tracking. Uncertainties are combined as if inputs are independent, which
  overstates the uncertainty where they are positively correlated. Conservative in the safe
  direction, and stated in the summary's method field.
- Units are unchecked strings. Mitigated by SI-everywhere and unit-suffixed config keys, not
  eliminated.
