# FlowForge Architecture

**Status:** design; M0 Quantity/provenance and units leaves implemented, other layers planned
**Scope:** the whole system, with V0 boundaries called out explicitly
**Audience:** anyone implementing, reviewing, or reproducing FlowForge

---

## 1. What this document decides

This is the top-level design. It fixes:

- the split of responsibility between microcontroller and host,
- the host language and runtime,
- the module boundaries and their dependency direction,
- how hardware is abstracted,
- how the simulator fits in,
- what is explicitly out of scope for V0.

Detailed designs live in sibling documents:

| Concern | Document |
| --- | --- |
| Host↔device wire protocol | [device-protocol.md](device-protocol.md) |
| On-disk experiment format | [data-format.md](data-format.md) |
| Physics, uncertainty, error budget | [measurement-model.md](measurement-model.md) |
| Calibration procedures and storage | [calibration.md](calibration.md) |
| Safety design | [safety.md](safety.md) |
| Known risks | [technical-risks.md](technical-risks.md) |
| Implementation plan | [v0-plan.md](v0-plan.md) |
| Hardware bill of materials | [../hardware/BOM.md](../hardware/BOM.md) |
| Justified decisions | [adr/](adr/) |

---

## 2. The one architectural idea

Everything else follows from this split:

> **The microcontroller owns time. The host owns meaning.**

The microcontroller does what a general-purpose OS cannot do reliably: sample sensors on a
deterministic schedule, timestamp every sample against one monotonic clock, drive the fan,
and enforce safety independently of whether the host is alive.

The host does what a microcontroller should not: interpret configuration, run the experiment
state machine, apply calibration, store raw data, compute aerodynamics, quantify uncertainty,
and produce reports.

Consequences that fall out of this and are non-negotiable:

- **The firmware never applies calibration.** It emits raw ADC counts *and* its best-effort SI
  conversion. The host stores both and always derives results from counts. If a calibration
  turns out to be wrong, every past experiment can be re-derived. See
  [ADR-0009](adr/0009-store-raw-counts-alongside-si.md).
- **The firmware never knows what an "experiment" is.** It knows `arm`, `set_fan`, `stream`,
  `heartbeat`, `stop`. Experiment semantics live entirely on the host.
- **The firmware is authoritative for safety.** The host can request a stop; the firmware
  will stop *anyway* if the host goes quiet. See [safety.md](safety.md).
- **The device clock is the measurement timebase.** Host wall-clock is recorded for human
  reference and mapped to the device clock by an explicit, stored clock model. See
  [ADR-0005](adr/0005-timebase-and-synchronisation.md).

---

## 3. Physical and logical layout

```text
                            ┌──────────────── camera (V3+) ─────────────┐
                            │                                           │
   ┌───────┐   ┌──────────┐ │ ┌───────────┐  ┌──────────────┐  ┌──────┐ │
   │ FANS  │──►│ SETTLING │─┴►│CONTRACTION│─►│ TEST SECTION │─►│DIFFUS│─┴─► exhaust
   │ array │   │ CHAMBER  │   │   4 : 1   │  │  100×100 mm  │  │ -ER  │
   └───────┘   │ honeycomb│   └───────────┘  └──────┬───────┘  └──────┘
       ▲       │ + screens│                         │
       │       └──────────┘                    specimen on sting
       │                                            │
       │                                      FORCE BALANCE ──┐
       │                                                      │
       │                              pitot-static ──┐        │
       │                              BME280 ────────┤        │
       │                                             ▼        ▼
       └──────── PWM + tach ◄──────────────── ESP32-S3 CONTROLLER
                                                     │
                                              USB CDC │ NDJSON, 921600
                                                     ▼
                                          ┌──────────────────────┐
                                          │   FlowForge host     │
                                          │   (Python, CLI)      │
                                          └──────────────────────┘
```

Airflow direction is left→right. The fans **push** into the settling chamber (blower
configuration) rather than pulling downstream of the test section, so that fan-blade wake and
swirl are conditioned out by the honeycomb and screens before reaching the specimen. See
[technical-risks.md](technical-risks.md#r-01-flow-quality) for the trade-off.

---

## 4. Host software architecture

### 4.1 Runtime

**Python 3.11+, managed with `uv`.** Rationale and rejected alternatives in
[ADR-0001](adr/0001-host-language-python.md). Short version: the entire deliverable of this
project is *numbers with defensible error bars*, and NumPy/SciPy/pandas/matplotlib is where
that work is cheapest and most reviewable. Real-time constraints are handled by the firmware,
so Python's weaknesses do not bind.

### 4.2 Layering

Dependencies point **downward only**. No module may import from a module above it.

```text
┌──────────────────────────────────────────────────────────────┐
│  apps            cli/  (typer)         dashboard/ (post-V0)  │
├──────────────────────────────────────────────────────────────┤
│  report          renders summary.json + processed.csv → md   │
│                  + plots. Knows nothing about hardware.      │
├──────────────────────────────────────────────────────────────┤
│  analysis        per-point aggregation, curve fitting,       │
│                  experiment comparison, compatibility checks │
├──────────────────────────────────────────────────────────────┤
│  aero            air density, pitot→velocity, q, Cd, Re,     │
│                  blockage, uncertainty propagation           │
├──────────────────────────────────────────────────────────────┤
│  signal          despike, filters, robust statistics,        │
│                  effective sample size, drift detection      │
├──────────────────────────────────────────────────────────────┤
│  experiments     config schema, state machine, run engine    │
├──────────────────────────────────────────────────────────────┤
│  storage         run directory layout, writers, readers,     │
│                  manifest + checksums, schema versioning     │
├──────────────────────────────────────────────────────────────┤
│  calibration     calibration records, fitting, resolution,   │
│                  application (counts → SI)                   │
├──────────────────────────────────────────────────────────────┤
│  acquisition     sample bus, ring buffers, clock model,      │
│                  dropout accounting, windowing               │
├──────────────────────────────────────────────────────────────┤
│  devices         Protocol definitions + backends:            │
│                  serial/ (real)   sim/ (simulated)           │
├──────────────────────────────────────────────────────────────┤
│  units, provenance, errors, logging  (leaf utilities)        │
└──────────────────────────────────────────────────────────────┘
```

Two rules keep this honest:

1. `aero`, `signal`, `analysis`, and `report` must be importable and fully testable **without
   any device present**. They take arrays and dataclasses, not connections.
2. `devices` is the *only* module that knows a serial port exists.

### 4.3 Repository layout

```text
flowforge/
├── pyproject.toml
├── README.md
├── src/flowforge/
│   ├── units.py            # SI everywhere; conversion only at I/O edges
│   ├── provenance.py       # MEASURED / DERIVED / ESTIMATED / ASSUMED / USER_PROVIDED
│   ├── quantity.py         # value + standard uncertainty + unit + provenance
│   ├── devices/
│   │   ├── interfaces.py   # typing.Protocol definitions
│   │   ├── registry.py     # config → backend construction
│   │   ├── serial/         # transport, codec, esp32 device
│   │   └── sim/            # simulated device (see §6)
│   ├── acquisition/
│   ├── calibration/
│   ├── signal/
│   ├── aero/
│   ├── experiments/
│   ├── storage/
│   ├── analysis/
│   ├── report/
│   └── cli/
├── firmware/flowforge-esp32/   # PlatformIO project
├── hardware/{bom,cad,electronics,wiring,assembly,calibration}/
├── examples/                   # example experiment configs + a canned run
├── tests/{unit,integration,hardware}/
└── docs/{...}/adr/
```

A single installable Python package, not a multi-package monorepo — see
[ADR-0002](adr/0002-single-python-package.md).

---

## 5. Device abstraction

Interfaces are `typing.Protocol` (structural), not inheritance hierarchies. A backend is a
class that satisfies the protocol; there is no base class to inherit and no plugin framework.
See [ADR-0007](adr/0007-device-abstraction-via-protocols.md).

```python
class FanController(Protocol):
    def set_duty(self, duty: float) -> None: ...        # 0.0 – 1.0, clamped by firmware
    def stop(self) -> None: ...                          # unconditional, always allowed
    def state(self) -> FanState: ...                     # duty, tach_hz, armed, faulted

class ForceSensor(Protocol):
    channel: str                                         # e.g. "drag"
    def tare(self, duration_s: float) -> TareResult: ...
    def latest(self) -> ForceSample | None: ...          # counts + SI + status

class AirspeedSensor(Protocol):
    def latest(self) -> DifferentialPressureSample | None: ...

class EnvironmentSensor(Protocol):
    def latest(self) -> EnvironmentSample | None: ...

class AngleController(Protocol):                         # declared in V0, implemented in V2
    def set_angle(self, deg: float) -> None: ...
    def angle(self) -> float: ...

class Instrument(Protocol):                              # the composite a run engine holds
    fan: FanController
    forces: Mapping[str, ForceSensor]
    airspeed: AirspeedSensor
    environment: EnvironmentSensor
    angle: AngleController | None
    def connect(self) -> DeviceInfo: ...
    def close(self) -> None: ...                         # must leave hardware safe
    def heartbeat(self) -> None: ...
```

Notes:

- Sensor reads are **pull-from-buffer**, not blocking device reads. The device streams
  continuously into an acquisition ring buffer; `latest()` and the windowing API read from
  that buffer. This is what makes multi-rate synchronisation tractable.
- `Instrument.close()` is a safety boundary and is called from a `finally` and an `atexit`
  hook. See [safety.md](safety.md).
- There is no `AngleController` hardware in V0. The protocol is declared so the experiment
  config schema and sweep engine can be written once; the V0 registry returns `None`.

---

## 6. The simulator

Mandatory, and treated as test infrastructure rather than a product feature
([ADR-0010](adr/0010-simulator-design.md)).

It exists at **two levels**, deliberately:

**Level 1 — `SimInstrument`.** Implements the device protocols in-process. Fast, used by the
majority of unit tests and by experiment-engine tests. Advances a *virtual clock*, so a
600-second sweep runs in milliseconds.

**Level 2 — `SimTransport`.** Implements the byte-level transport interface and speaks the
real NDJSON protocol, driven by the same plant model. Used by protocol/codec tests and by at
least one end-to-end integration test, so the wire format, framing, sequence-number handling,
timeout logic, and clock-offset estimator are all exercised in CI without hardware.

The plant model, shared by both:

| Element | Model |
| --- | --- |
| Fan dynamics | first-order lag, `τ ≈ 1.5 s`, on the duty→speed map |
| Duty→speed | affine above a stall duty: `v_ss = max(0, a·(d − d₀))`, from a fitted curve |
| Turbulence | Ornstein–Uhlenbeck process added to `v`, configurable intensity |
| Drag | `F = ½ρv²·A·Cd(Re) + F_fixture(v)` with a configurable ground-truth `Cd` |
| Load cell | force → counts via the *inverse* of a calibration record, + white noise + 1/f drift + quantisation |
| Pitot | `Δp = ½ρv²/k²` + offset drift + noise |
| Environment | slowly varying T, p, RH |
| Faults | injectable: sample dropout, disconnect, stuck channel, saturation, NaN, late heartbeat |

Everything is seeded. Same seed ⇒ byte-identical run directory (modulo the recorded wall-clock
stamp). The headline acceptance test is: *configure ground-truth `Cd = 0.47`, run the standard
sweep, and require the recovered `Cd` to bracket 0.47 within its own stated expanded
uncertainty* — which tests the analysis chain and the uncertainty model at the same time.

---

## 7. Firmware architecture

**ESP32-S3, PlatformIO, Arduino-ESP32 framework over FreeRTOS.** Rationale in
[ADR-0003](adr/0003-firmware-esp32-freertos.md).

Three tasks, explicitly prioritised:

```text
core 1 ┌─ acquisition task   prio HIGH, 1 kHz tick
       │    · NAU7802 DRDY-driven force read      (80–320 Hz)
       │    · SDP810 read                          (50 Hz)
       │    · BME280 read                          (1 Hz)
       │    · tachometer edge counting             (continuous)
       │    · timestamps every sample: esp_timer_get_time() µs
       │    └─► lock-free SPSC queue
       │
core 0 ├─ comms task         prio NORMAL
       │    · drains queue → NDJSON → USB CDC
       │    · parses inbound commands, replies with ack/err
       │    └─► posts actuator requests to the control task
       │
core 0 └─ control+safety task prio HIGH, 100 Hz tick
            · heartbeat watchdog (500 ms)
            · duty ramp limiter, hard duty ceiling
            · fault latch; drives LEDC PWM
            · hardware TWDT subscription
```

Structure inside the firmware separates *what* from *how*, so a different MCU or a different
load-cell ADC is a file swap, not a rewrite:

```text
firmware/flowforge-esp32/src/
├── main.cpp
├── proto/          # message encode/decode — portable, unit-testable on host
├── safety/         # watchdog, fault latch, limits — no hardware includes
├── control/        # fan duty state machine, ramp limiting
└── hal/            # board pinmap + one file per sensor driver
    ├── board.h
    ├── adc_nau7802.cpp   (alt: adc_hx711.cpp)
    ├── dp_sdp8xx.cpp
    ├── env_bme280.cpp
    └── fan_ledc.cpp
```

`proto/` and `safety/` compile natively and are tested under `pio test -e native` in CI — no
board required.

---

## 8. Acquisition and synchronisation

Every sample carries `t_dev`, the device's monotonic microsecond counter. That is the only
timebase measurements are compared on.

The host maintains a **clock model** mapping `t_dev → t_host`:

- The host sends `ping` at 1 Hz; the device replies immediately with its `t_dev`.
- The host records `(t_send, t_dev, t_recv)`, discards exchanges with high round-trip time,
  and fits `t_host ≈ α·t_dev + β` by robust linear regression over a rolling window.
- `α` captures crystal skew (tens of ppm); `β` captures offset.
- The fitted `(α, β)`, its residual spread, and the raw ping exchanges are **written into the
  run directory**, so a later reader can re-derive host time or reject the mapping.

Nothing in the analysis path depends on host time. This matters most later, when camera
frames must be aligned to force samples ([ADR-0005](adr/0005-timebase-and-synchronisation.md)).

Dropouts: every telemetry message carries a per-channel monotonic `seq`. Gaps are detected,
counted, logged as events, and reported in the summary. A test point whose dropout fraction
exceeds a configurable threshold is flagged, not silently averaged over.

---

## 9. Experiment engine

An explicit state machine, not a sequence of sleeps ([ADR-0008](adr/0008-experiment-state-machine.md)).

```text
                      ┌──────────────────────────────────────────┐
                      ▼                                          │
CREATED → VALIDATING → CONNECTING → ZEROING → BASELINE? → SETTING_CONDITION
                                                                 │
                                                                 ▼
                                                           STABILISING
                                                                 │
                                                                 ▼
                                                            SAMPLING
                                                                 │
                                        ┌────────────────────────┤
                                   more points                 done
                                        │                        ▼
                                        └──────────────────► STOPPING → ANALYSING → COMPLETED

any state ──► ABORTING ──► FAILED(reason) | ABORTED
```

Failure reasons are a closed enum: `SENSOR_FAILURE`, `DEVICE_DISCONNECTED`,
`AIRFLOW_UNSTABLE`, `SPEED_UNREACHABLE`, `CALIBRATION_MISSING`, `CALIBRATION_EXPIRED`,
`OVERLOAD`, `USER_ABORTED`, `HOST_ERROR`.

Invariants enforced by the engine:

- Every transition is timestamped and appended to `raw/events.jsonl` **before** the action.
- `ABORTING` is reachable from every state and its first action is `fan.stop()`.
- Raw sample writing starts at `CONNECTING` and stops at `STOPPING` — including during
  stabilisation and transitions, so the whole run is inspectable, not just the sample windows.
- `ANALYSING` reads only from files already written. If analysis crashes, the run directory is
  still a complete, re-analysable record. `flowforge analyze <run>` re-runs that stage offline.

---

## 10. Data flow for one test point

```text
firmware ──NDJSON──► codec ──► clock model ──► ring buffer ──► raw/samples.csv   [counts + SI]
                                                    │                (append, never rewritten)
                                                    │
                                    window [t_start, t_end] selected by engine
                                                    │
                                                    ▼
                                        calibration (counts → N, Pa, K…)
                                                    │
                                                    ▼
                                    signal: despike → robust stats → N_eff
                                                    │
                                                    ▼
                                    aero: ρ(T,p,RH), v(Δp,ρ,k), q, Cd, Re
                                                    │
                                                    ▼
                                    uncertainty propagation (GUM)
                                                    │
                                                    ▼
                                    processed/points.csv + results/summary.json
```

`raw/samples.csv` is append-only and is never modified by any later stage. Every downstream
artefact is a pure function of the raw file plus `calibration.json` plus `run.yaml` — which is
what makes `flowforge analyze` able to reproduce a result months later, and what lets a
corrected calibration be applied retroactively.

---

## 11. Units and provenance

- **SI internally, always.** Newtons, metres/second, pascals, kelvin, kilograms, seconds.
  Conversions (°C, mm, g, %) happen only in the CLI display layer and when parsing config,
  and config keys carry their unit in the name (`reference_area_m2`, `chord_mm`).
- Every reported quantity carries a **provenance tag**: `MEASURED`, `DERIVED`, `ESTIMATED`,
  `ASSUMED`, `USER_PROVIDED`. These are stored in `summary.json`, printed in the CLI report,
  and shown in plot annotations. `Cd` is `DERIVED`; reference area is `USER_PROVIDED`; air
  density is `DERIVED` from measured T/p/RH but becomes `ASSUMED` if the BME280 is absent.
- Every quantity that will be reported carries a **standard uncertainty**. Formatting rounds
  the uncertainty to two significant figures and the value to the same decimal place. There is
  no code path that prints a bare float as a result. See
  [measurement-model.md](measurement-model.md).

---

## 12. Observability

Structured logging (`structlog`-style key/value into stdlib `logging`), two sinks:

- console — human, INFO, progress-oriented, no raw samples ever;
- `raw/events.jsonl` — machine, DEBUG-capable, part of the experiment record.

Always logged: device connect/disconnect with firmware version and hardware IDs, every fan
command, every state transition, calibration records loaded (with IDs and dates), achieved vs
requested sample rate per channel, dropped-sample counts, stabilisation outcome, every
warning, every fault.

Never logged at INFO: individual samples. `--debug-samples` exists and is off by default.

---

## 13. Explicit V0 boundaries

**In V0:** single drag axis; fixed specimen angle; open-loop fan duty with a calibrated
duty→speed map plus a verification check against the measured airspeed; fixed-duration
stabilisation with a statistical stability *check*; CSV + JSON storage; static matplotlib
plots; CLI only.

**Deliberately not in V0:** lift axis, motorised angle sweeps, camera, PIV, CFD import,
optimisation, dashboard, closed-loop PID airflow control, networking of any kind, Parquet,
multi-user anything.

Where a V0 choice would foreclose a later milestone, the seam is named here and nowhere else:

| Later milestone | Seam already present in V0 |
| --- | --- |
| V1 two-axis balance | `forces` is a `Mapping[str, ForceSensor]`, not a single sensor; storage is long-format, so a `lift` channel adds rows, not columns |
| V2 angle sweeps | `AngleController` protocol declared; sweep config is `parameter: airspeed \| angle`; state machine's `SETTING_CONDITION` is parameter-agnostic |
| V3/V4 camera, PIV | device-clock timebase and stored clock model make frame↔force alignment a lookup, not an inference |
| V5 CFD comparison | `summary.json` carries geometry references, Re, and reference area, which is what a comparison needs |
| V6 optimisation | specimen records carry parameter dictionaries; a run is addressable by specimen revision |

None of these cost anything today. Anything that *would* cost something today was left out.
