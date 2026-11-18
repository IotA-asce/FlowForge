<h1 align="center">FlowForge</h1>

<p align="center">
  <strong>An open-source automated desktop wind tunnel.</strong><br>
  Turn 3D-printed designs into reproducible aerodynamic data.
</p>

<p align="center">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg">
  <img alt="Status: design phase" src="https://img.shields.io/badge/status-design%20phase-orange.svg">
  <img alt="V0 progress: 0 of 11 milestones" src="https://img.shields.io/badge/V0%20progress-0%2F11%20milestones-lightgrey.svg">
</p>

---

> [!IMPORTANT]
> **M0 is partially implemented; this is not yet a working drag bench.**
>
> Architecture, wire protocol, data format, measurement model, calibration procedures,
> safety analysis, hardware design, and twelve architecture decision records guide
> implementation. The current foundation is described below and tracked under
> **M0** in [docs/v0-plan.md](docs/v0-plan.md); the first
> milestone that produces a result is a fully simulated drag sweep, with no hardware involved.

## Why

Most hobby wind tunnels are demonstrations: you turn a knob, a flag flutters, and you get a
feeling. FlowForge is built to behave like an instrument instead — one that produces numbers you
can defend, compare, and publish.

The success condition is not features. It is this:

> If the same specimen is tested twice under the same conditions, FlowForge should produce
> meaningfully repeatable measurements and preserve enough information to explain exactly how
> those measurements were obtained.

Everything in the design follows from that sentence: raw data is never overwritten, every
reported number carries an uncertainty and a provenance tag, and calibration is a dated,
traceable record rather than a constant in a source file.

## How it works

```text
   ┌───────┐   ┌──────────┐   ┌───────────┐  ┌──────────────┐  ┌──────────┐
   │ FANS  │──►│ SETTLING │──►│CONTRACTION│─►│ TEST SECTION │─►│ DIFFUSER │──► exhaust
   │ 4× PWM│   │ honeycomb│   │   4 : 1   │  │  100×100 mm  │  └──────────┘
   └───────┘   │ + screens│   └───────────┘  └──────┬───────┘
       ▲       └──────────┘                         │  specimen on a sting
       │                                            ▼
       │                                     FORCE BALANCE ─────┐
       │                          pitot-static ──┐              │
       │                          BME280 ────────┤              │
       │                                         ▼              ▼
       └──────── PWM + tach ◄────────────  ESP32-S3 CONTROLLER
                                                  │  USB CDC · NDJSON
                                                  ▼
                                        ┌────────────────────┐
                                        │  FlowForge (host)  │
                                        └────────────────────┘
```

You mount a printed specimen, write a short YAML file, and run one command. FlowForge sets the
airflow, waits for the flow to settle, samples force and flow sensors on a synchronised
timeline, steps to the next speed, and writes a self-contained run directory.

## Implemented software foundation

The first **M0 subset** is implemented: immutable quantities, the five provenance
labels, computed-origin propagation, and uncertainty-aware formatting. This is
not yet the simulator, instrument CLI, acquisition pipeline or hardware control.

Static import-direction checks enforce the documented layers, including indirect
device dependencies from scientific layers. GitHub Actions runs locked tests,
strict typing, lint, source/test formatting and package builds on Ubuntu with
Python 3.11 and 3.13 for pushes and pull requests. See
[software validation](docs/software-validation.md). Units/errors/logging helpers
remain TODO; adding CI does not by itself complete M0.

```bash
uv sync --locked --python 3.11
uv run --locked pytest
uv run --locked mypy
uv run --locked ruff check .
uv run --locked ruff format --check src tests
```

The documented numeric example is a formatting fixture, not a measured run:

```python
from flowforge.provenance import Provenance
from flowforge.quantity import Quantity

print(Quantity(0.4712, 0.0937, "", Provenance.DERIVED))
# 0.471 ± 0.094 [DERIVED]
```

See [metrology-primitives.md](docs/metrology-primitives.md) for standard versus
expanded uncertainty, provenance, and unresolved/unknown warnings. **M0 remains
partial:** units/errors/logging helpers, import-direction checks and CI are TODO.
The planned commands below remain unavailable until their later milestones.

## Planned interface

> The commands below describe the intended V0 interface. They do not run yet.

```console
$ flowforge run experiments/sphere-25mm.yaml

Connecting to ff-esp32-0A1B2C (fw 0.3.1)... ok
Calibration: loadcell-drag-2026-08-01-a (6 days old), pitot-2026-08-03-a (4 days old)
Zeroing balance... 30 s, sd 41 counts, drift 0.4 counts/s  ok

  4.0 m/s   stabilising 8 s   sampling 12 s   F = 2.2 ± 1.1 mN   ⚠ SNR_MARGINAL
  6.0 m/s   stabilising 8 s   sampling 12 s   F = 5.1 ± 1.1 mN
  8.0 m/s   stabilising 8 s   sampling 12 s   F = 8.9 ± 1.2 mN
 ...
 18.0 m/s   stabilising 8 s   sampling 12 s   F = 44.6 ± 2.1 mN

Post-sweep tare... zero return 0.69 mN  ok
Analysing...

  Cd = 0.471 ± 0.094        DERIVED   (k = 2)
  F ∝ v^1.97 ± 0.05         DERIVED   (expected 2.00)
  Re = 6.6e3 … 3.0e4        DERIVED

  1 warning: HIGH_BLOCKAGE (S/C = 4.9%)

Written to experiments/2026-08-07_142233_sphere-25mm/
```

```console
$ flowforge compare cube-25mm sphere-25mm teardrop-25mm

Drag @ 15.0 m/s (interpolated from fitted curves)

  Cube        88.6 ± 3.8 mN    1.00×
  Sphere      31.1 ± 2.6 mN    0.35×
  Teardrop     8.0 ± 2.1 mN    0.09×   ⚠ SNR_MARGINAL

  ⚠ teardrop-25mm used a different load-cell calibration record
```

Every number that reaches a report carries an uncertainty and one of five provenance tags —
`MEASURED`, `DERIVED`, `ESTIMATED`, `ASSUMED`, `USER_PROVIDED`. There is no code path that
prints a bare float as a result.

## V0 scope

**In:** one drag axis, fixed specimen orientation, automatic airspeed sweeps from 4 to 18 m/s in
a 100 × 100 mm test section, calibration and taring, raw-data retention, drag curves, drag
coefficients with uncertainties, and experiment comparison.

**Out, deliberately:** lift, motorised angle sweeps, cameras, PIV, CFD import, optimisation, a
dashboard, closed-loop airflow control, and networking of any kind. The seams for each are
identified in [docs/architecture.md §13](docs/architecture.md#13-explicit-v0-boundaries), and
none of them cost anything today.

## Documentation

| Document | What it covers |
| --- | --- |
| [architecture.md](docs/architecture.md) | System design, layering, module boundaries, simulator |
| [v0-plan.md](docs/v0-plan.md) | Milestones M0–M10, each with a machine-checkable acceptance test |
| [measurement-model.md](docs/measurement-model.md) | Every formula and constant; the full error budget; what V0 can and cannot claim |
| [device-protocol.md](docs/device-protocol.md) | Host↔device wire protocol, version 1 |
| [data-format.md](docs/data-format.md) | Run directory layout and every file schema |
| [calibration.md](docs/calibration.md) | Procedures, acceptance criteria, storage, verification |
| [safety.md](docs/safety.md) | Hazard register, safety requirements, failure-mode analysis |
| [technical-risks.md](docs/technical-risks.md) | Ranked risks, each with a detection strategy |
| [hardware/BOM.md](hardware/BOM.md) | Provisional bill of materials, written requirement-first |
| [adr/](docs/adr/) | Twelve architecture decision records |

New to the project? Read [architecture.md](docs/architecture.md), then
[measurement-model.md](docs/measurement-model.md). The second one is where the engineering
actually lives.

## Design decisions at a glance

| Decision | Why |
| --- | --- |
| **The microcontroller owns time; the host owns meaning** | An ESP32-S3 timestamps every sample on its monotonic clock. At 15 m/s, 10 ms of host jitter is 150 mm of flow. ([ADR-0005](docs/adr/0005-timebase-and-synchronisation.md)) |
| **Raw ADC counts are stored, never just newtons** | A calibration found wrong later can be corrected retroactively and every past run re-derived. ([ADR-0009](docs/adr/0009-store-raw-counts-alongside-si.md)) |
| **Uncertainty and provenance are types, not conventions** | False precision becomes structurally hard to emit rather than merely discouraged. ([ADR-0012](docs/adr/0012-uncertainty-and-provenance-types.md)) |
| **Experiments are directories of CSV and JSON** | A stranger can check your data with a text editor and a spreadsheet. ([ADR-0006](docs/adr/0006-run-directory-csv-json.md)) |
| **The firmware, not the host, is authoritative for safety** | Lose the heartbeat for 500 ms and the fan stops, latched — and never restarts on its own. ([safety.md](docs/safety.md)) |
| **The simulator is mandatory infrastructure** | The entire stack, wire protocol included, is proven in CI before any hardware is connected. ([ADR-0010](docs/adr/0010-simulator-design.md)) |

## What the measurement model promises

Design estimates, to be replaced with measured values in milestones M8c and M9:

| Quantity | Expanded (k = 2) |
| --- | --- |
| Force | **±2 mN ⊕ 2.4 %**, before support-interference effects |
| `Cd`, bluff bodies | **±20 %** — e.g. `Cd = 0.47 ± 0.09` for a 25 mm sphere at 15 m/s |
| `Cd`, streamlined bodies | **not claimed in V0** — the signal approaches the support-drag uncertainty |

Three findings shaped the whole design, and all three are worked through in
[measurement-model.md](docs/measurement-model.md):

- **Support drag is the dominant systematic.** A bare 4 mm sting produces ~36 mN at 15 m/s; a
  25 mm sphere produces ~31 mN. The support can out-drag the specimen.
- **Air density cancels out of `Cd` exactly.** Since `v = k√(2Δp/ρ)`, `Cd = F/(k²·Δp·A)` — so
  the pitot factor, which enters *squared*, is the highest-leverage calibration after the load
  cell.
- **The cube, not the sphere, is the reference specimen.** Sharp-edged bodies have fixed
  separation points, making them insensitive to Reynolds number and to the turbulence intensity
  a short open-circuit tunnel will inevitably have.

## Roadmap

| | Milestone | Adds |
| --- | --- | --- |
| **V0** | Automated drag bench | Fan control, airspeed, drag force, sweeps, calibration, analysis, comparison |
| V1 | Two-axis force balance | Lift, `Cl`, enclosure interlock |
| V2 | Motorised angle-of-attack sweeps | Lift and drag curves, L/D, stall detection |
| V3 | Flow visualisation | Smoke, illumination, synchronised video |
| V4 | Particle image velocimetry | Velocity fields, wake structure, vorticity |
| V5 | CFD comparison | Import OpenFOAM results, compare predicted against measured |
| V6 | Physical design optimisation | Parametric specimens driven by real measurements |

Nothing beyond V0 is implemented, and nothing beyond V0 is started until V0 produces repeatable
measurements.

## Repository layout

```text
docs/            architecture, protocol, data format, measurement model, safety, risks
docs/adr/        architecture decision records
hardware/        bill of materials; CAD, wiring, and assembly to follow
                 (planned: src/flowforge/ · firmware/ · tests/ · examples/)
```

## Safety

FlowForge drives a fan array and can accelerate a loose specimen to 18 m/s. Before building or
running anything, read [docs/safety.md](docs/safety.md).

The two hazards that can cause permanent injury are **specimen ejection** — which is why
specimens are retained with a screw and the test section is polycarbonate rather than acrylic —
and **laser exposure** in the eventual PIV milestone, which is gated behind its own safety
document.

## Contributing

The project is pre-implementation, so the most valuable contributions right now are review
rather than code:

- Errors in [measurement-model.md](docs/measurement-model.md) — a wrong formula or an
  underestimated uncertainty is the most expensive kind of bug this project can have.
- Gaps in [technical-risks.md](docs/technical-risks.md) or [safety.md](docs/safety.md).
- Component suggestions for [hardware/BOM.md](hardware/BOM.md), which is written
  requirement-first precisely so that substitutions are easy to evaluate.

Decisions that would be expensive to reverse are recorded as ADRs. If you disagree with one,
the ADR is the place to argue with it — each states the alternatives it beat and the drawbacks
it accepted.

## License

[MIT](LICENSE) © 2026 Mu In Nasif
