# FlowForge

An open-source automated desktop wind tunnel that turns 3D-printed designs into reproducible
aerodynamic data.

> **Status: design phase.** This repository currently contains the architecture, protocol, data
> format, measurement model, and hardware design. **No code has been written yet.** The first
> implementation milestone is a fully simulated drag sweep — see
> [docs/v0-plan.md](docs/v0-plan.md).

---

## What it will do

Place a 3D-printed specimen in the tunnel and run:

```bash
flowforge run experiments/sphere-25mm.yaml
```

FlowForge sets the airflow speed, waits for the flow to stabilise, samples force and flow
sensors on a synchronised timeline, steps to the next speed, and produces a run directory
containing the raw samples, the calibration used, per-point statistics, drag coefficients with
uncertainties, and a report.

The point is not automation for its own sake. It is this:

> If the same specimen is tested twice under the same conditions, FlowForge should produce
> meaningfully repeatable measurements and preserve enough information to explain exactly how
> those measurements were obtained.

## V0 scope

One drag axis, fixed specimen orientation, automatic airspeed sweeps from 4 to 18 m/s in a
100 × 100 mm test section, with honest error bars. Lift, angle sweeps, flow visualisation, PIV,
CFD comparison, and design optimisation are later milestones and are deliberately absent.

## Documentation

| Document | What it covers |
| --- | --- |
| [docs/architecture.md](docs/architecture.md) | System design, layering, module boundaries |
| [docs/v0-plan.md](docs/v0-plan.md) | Milestones M0–M10, each with a machine-checkable acceptance test |
| [docs/measurement-model.md](docs/measurement-model.md) | Every formula and constant; the full error budget; what V0 can and cannot claim |
| [docs/device-protocol.md](docs/device-protocol.md) | Host↔device wire protocol |
| [docs/data-format.md](docs/data-format.md) | Run directory layout and every file schema |
| [docs/calibration.md](docs/calibration.md) | Calibration procedures, acceptance criteria, storage |
| [docs/safety.md](docs/safety.md) | Hazard register, safety requirements, failure-mode analysis |
| [docs/technical-risks.md](docs/technical-risks.md) | Ranked risks with detection strategies |
| [hardware/BOM.md](hardware/BOM.md) | Provisional bill of materials, requirement-first |
| [docs/adr/](docs/adr/) | Architecture decision records |

## Key decisions at a glance

- **The microcontroller owns time; the host owns meaning.** An ESP32-S3 timestamps every sample
  on its monotonic clock and enforces safety independently of the host. Python does
  configuration, calibration, analysis, and reporting. ([ADR-0001](docs/adr/0001-host-language-python.md),
  [ADR-0003](docs/adr/0003-firmware-esp32-freertos.md), [ADR-0005](docs/adr/0005-timebase-and-synchronisation.md))
- **Raw ADC counts are stored, never just newtons.** A calibration found to be wrong later can be
  corrected retroactively, and every past run re-derived. ([ADR-0009](docs/adr/0009-store-raw-counts-alongside-si.md))
- **Every reported number carries an uncertainty and a provenance tag** — measured, derived,
  estimated, assumed, or user-provided — enforced by the type system rather than by convention.
  ([ADR-0012](docs/adr/0012-uncertainty-and-provenance-types.md))
- **Experiments are directories of CSV and JSON**, inspectable without FlowForge installed.
  ([ADR-0006](docs/adr/0006-run-directory-csv-json.md))
- **The firmware, not the host, is authoritative for safety.** Lose the heartbeat for 500 ms and
  the fan stops, latched — and never restarts on its own. ([docs/safety.md](docs/safety.md))
- **A simulator is mandatory infrastructure.** The whole software stack, including the wire
  protocol, is proven in CI before any hardware is connected. ([ADR-0010](docs/adr/0010-simulator-design.md))

## What the measurement model actually promises

Design estimates, to be replaced with measured values during M8c and M9:

- Force: **±2 mN ⊕ 2.4 %** expanded (k=2), before support-interference effects.
- Drag coefficient for bluff bodies: **±20 %** expanded, e.g. `Cd = 0.47 ± 0.09` for a 25 mm
  sphere at 15 m/s.
- Repeatability, not absolute accuracy, is the headline claim. Streamlined-body `Cd` is **not**
  credible in V0 and the reports say so.

The reasoning, including why air density cancels out of `Cd` entirely and why support drag is
the dominant systematic, is in [docs/measurement-model.md](docs/measurement-model.md).

## License

MIT — see [LICENSE](LICENSE).
