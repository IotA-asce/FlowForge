# FlowForge Safety

FlowForge drives a fan array capable of moving ~300 CFM through a 100 × 100 mm duct at up to
18 m/s, and later moves specimens under motor control. The hazards are modest but real, and
several of them are the kind that only bite when something *else* has already gone wrong —
which is exactly when a design that relies on the host being alive fails.

Governing principle:

> **Safety is enforced by the firmware, not by the host, and the physical emergency stop is
> enforced by neither.**

---

## 1. Hazard register

| ID | Hazard | Severity | Likelihood | Primary control |
| --- | --- | --- | --- | --- |
| H-1 | Contact with rotating fan blades | Moderate (laceration) | Low | Finger guards on inlet and exhaust; fans not reachable without tools |
| H-2 | Specimen detaches and is ejected at flow speed | **High (eye injury)** | Medium | Positive mechanical retention (screw, not friction fit); closed test section; downstream catch screen; eye protection |
| H-3 | Fragment of a printed part or fastener ejected | Moderate | Medium | Same as H-2; pre-run visual check in the assembly checklist |
| H-4 | Acoustic exposure from the fan array | Moderate (cumulative) | **High** | Measure dBA at the operator position; hearing protection above 80 dBA; duty-cycle limits |
| H-5 | Electrical fault in the 12 V / ~5 A fan supply | Moderate (fire) | Low | Fused supply, correctly rated wiring, no exposed conductors, enclosure |
| H-6 | Fan stall / blocked inlet causing overheating | Moderate | Low | Tachometer stall detection → fault; thermal margin in fan selection |
| H-7 | Load-cell overload from handling or a runaway force | Low (equipment) | Medium | Mechanical hard stop at ~150 % of range; saturation detection → abort |
| H-8 | Trailing cables / tunnel tipping off the bench | Low | Medium | Bench fixing, cable strain relief; documented in assembly |
| H-9 | Pinch by the angle motor (V2) | Low | Medium | Software angle limits, low-torque servo, motion only while `ARMED` |
| H-10 | Fog fluid / particulate inhalation (V3) | Moderate | Medium | Ventilation requirement; out of V0 scope, flagged now |
| H-11 | Laser exposure (V4 PIV) | **High (eye)** | Medium | Not in scope for V0. **A PIV sheet laser is a Class 3B-class hazard and requires its own safety document, interlocks, and controlled access before any implementation begins.** |

H-2 and H-11 are the two that can cause permanent injury. H-2 is in scope now.

---

## 2. Software safety requirements

Each requirement has an ID, an owner (firmware or host), and a verification method. These are
testable statements, not aspirations.

| ID | Requirement | Owner | Verified by |
| --- | --- | --- | --- |
| SR-1 | On power-on and on reset, fan duty is 0 and the device is `IDLE` (disarmed). No stored duty is restored. | firmware | HIL test: power cycle while a duty is commanded |
| SR-2 | If no `heartbeat` is received for 500 ms while `ARMED`, the device sets duty 0 within one control tick (10 ms) and latches `HEARTBEAT_TIMEOUT`. | firmware | `pio test -e native` on the safety module; HIL test: kill the host process |
| SR-3 | Loss of USB (DTR deasserted, or CDC closed) sets duty 0 and latches `USB_DISCONNECT`. | firmware | HIL test: unplug the cable mid-sweep |
| SR-4 | After any fault or reconnection, the fan **never** restarts without a fresh explicit `arm` from the host. Reconnection alone must not spin a fan. | firmware | HIL test: unplug and replug mid-sweep; assert duty stays 0 |
| SR-5 | A compile-time `HARD_MAX_DUTY` ceiling clamps every duty request. `set_limits` may only lower it, never raise it. | firmware | native unit test |
| SR-6 | Duty changes are rate-limited to `ramp_per_s` (default 0.5 /s). No step change reaches the fan. | firmware | native unit test; scope trace on the PWM line |
| SR-7 | `stop` is accepted and executed in **every** device state, including `FAULTED`, and is never queued behind another command. | firmware | native unit test |
| SR-8 | The host stops the fan on every exit path: normal completion, exception, `KeyboardInterrupt`, `SIGTERM`, and interpreter shutdown. | host | unit tests injecting each exit path against `SimInstrument` |
| SR-9 | `ABORTING` is reachable from every experiment state and its **first** action is `fan.stop()`, before any logging or teardown. | host | state-machine property test over all states |
| SR-10 | Load-cell ADC saturation (`SATURATED` status) for more than 200 ms aborts the run with `OVERLOAD`. | host | simulator fault injection |
| SR-11 | Duty commanded above `d₀` with the tachometer reading zero for 2 s latches `TACH_STALL`. | firmware | HIL test: block a fan inlet |
| SR-12 | `arm` is refused while any fault is latched. | firmware | native unit test |
| SR-13 | A run exceeding `safety.max_run_seconds` (default 3600) aborts. | host | unit test with a virtual clock |
| SR-14 | The E-stop state is readable by the firmware and reported in telemetry, but the E-stop's *action* does not depend on the firmware. | hardware + firmware | inspection + HIL test |

### 2.1 Host-side stop paths (SR-8)

```python
def run(...):
    instrument = registry.build(config)
    try:
        with fan_safety(instrument):     # __exit__ calls stop() unconditionally
            engine.execute()
    finally:
        instrument.close()               # close() also stops, idempotently

# registered at construction, not at run start:
atexit.register(instrument.emergency_stop)
signal.signal(signal.SIGTERM, _stop_and_reraise)
signal.signal(signal.SIGINT,  _stop_and_reraise)
```

`emergency_stop()` bypasses the command queue and the ack-wait: it writes a single `stop` line
straight to the transport and does not block on a reply. A host that is dying cannot afford a
250 ms round trip, and SR-2 covers it if the write never lands.

---

## 3. The emergency stop

A **latching mushroom-head switch interrupting the fan supply**, not a GPIO input to the
microcontroller.

```text
12 V PSU ──[ fuse ]──[ E-STOP, NC latching ]──┬── fan array
                                              │
                                              └──[ divider ]── ESP32 GPIO (sense only)
```

Properties this buys:

- Pressing it removes fan power regardless of firmware state, host state, or a hung MCU.
- It latches, so releasing it is a deliberate two-handed act (twist to release).
- The MCU keeps its own 5 V USB supply, so it stays alive, sees the sense line drop, latches an
  `ESTOP` fault, and reports it. The instrument therefore *records* the emergency stop in
  `raw/events.jsonl` rather than merely surviving it.
- Releasing the E-stop restores fan *power* but not fan *command*: the latched fault means duty
  stays 0 until an explicit `clear_fault` + `arm`. Per SR-4, nothing spins on its own.

Placement: within arm's reach of the operator position, never behind the tunnel.

---

## 4. Mechanical controls

**Specimen retention (H-2), the most important physical control.** Specimens attach to the
sting with a **positive mechanical fastener** — an M3 screw through the sting into a printed
insert, or a threaded stud. Friction, magnets, and press fits are not acceptable, because the
failure mode of a friction fit at 18 m/s is a projectile.

Supporting controls:

- The test section is fully enclosed in ≥3 mm polycarbonate (not acrylic — polycarbonate is far
  more impact-tolerant and does not shatter into fragments).
- A coarse screen downstream of the test section catches anything that does come loose before
  it reaches the exhaust.
- Pre-run checklist item: tug-test the specimen, confirm the fastener is seated.
- Eye protection while the tunnel is running is stated in the assembly and operation docs.

**Load-cell protection (H-7).** A mechanical hard stop limits balance travel to roughly 150 %
of the load cell's rated deflection, so mishandling cannot yield the element. This costs a
printed bracket and saves the most sensitive component in the machine.

**Guarding (H-1).** Wire finger guards on the fan inlet; the exhaust diffuser is long enough
that blades are not reachable. Fans are inside the enclosure and not accessible without tools.

**Noise (H-4).** A four-fan high-static-pressure array is genuinely loud — expect 65–80 dBA at
one metre at full duty. Measure it once with a phone SPL app, record the figure in the assembly
documentation, and put hearing protection in the BOM if it exceeds 80 dBA. Sweeps are minutes
long and repeated often; this is a cumulative exposure, not a nuisance.

---

## 5. Failure-mode analysis

| Failure | Detection | Response | Physical outcome |
| --- | --- | --- | --- |
| Host process crashes | heartbeat timeout (SR-2) | firmware duty 0, latch | fan spins down |
| Host hangs (deadlock, GC pause > 500 ms) | heartbeat timeout | duty 0, latch | fan spins down; run aborts |
| USB cable pulled | DTR deassert (SR-3) | duty 0, latch | fan spins down |
| MCU crashes / hangs | hardware task watchdog | MCU reset; boots to `IDLE`, duty 0 (SR-1) | fan spins down |
| MCU reset loop | host sees `boot_count` increment + repeated `hello` | host aborts run | fan off between resets |
| PWM output stuck high (hardware fault) | tachometer reads high with duty 0 | latch `TACH_MISMATCH`, report | **E-stop is the only remedy** — documented |
| Fan blocked / seized | tach stall (SR-11) | duty 0, latch | prevents overheating |
| Load cell saturated | status bit (SR-10) | abort run, fan 0 | protects the cell |
| Sensor bus (I²C) lockout | NACK/CRC retries exhausted | latch `SENSOR_TIMEOUT`, duty 0 | run aborts with data intact |
| Power loss | — | everything stops | safe by construction |
| Specimen detaches | not detectable in software | — | **relies entirely on physical controls (§4)** |

The last row is the important one. It is the reason specimen retention is a screw and the test
section is polycarbonate: there is no software mitigation, so the mechanical control has to be
sufficient on its own.

---

## 6. Operating limits

| Limit | Default | Where enforced |
| --- | --- | --- |
| `HARD_MAX_DUTY` | 0.95 | firmware, compile time |
| `max_fan_duty` | 0.90 | run config, cannot exceed the above |
| `ramp_per_s` | 0.5 /s | firmware |
| `heartbeat_timeout_ms` | 500 | firmware |
| `max_run_seconds` | 3600 | host |
| `max_continuous_fan_seconds` | 900 | host; forces a cool-down pause |
| angle limits (V2) | ±30° | firmware, and mechanical hard stops |

Config may only tighten these. There is no code path that widens a firmware limit from the host
— `set_limits` clamps to the compile-time ceiling and returns the clamped value in its `ack`,
so an over-ambitious config is visible in the log rather than silently obeyed or silently
ignored.

---

## 7. Operating procedure (summary)

Pre-run:

1. Test section closed and latched; polycarbonate undamaged.
2. Specimen fastener seated; tug-test passed.
3. Nothing loose inside the tunnel; catch screen in place.
4. E-stop within reach and released.
5. Eye protection on; hearing protection if the measured level requires it.

During:

- Do not open the test section while `ARMED`. Interlocking the enclosure is a worthwhile V1
  addition and is noted in [technical-risks.md](technical-risks.md).

Post-run:

- Confirm duty 0 and the device is `IDLE` before opening.
- Review the run's warnings before trusting any number in it.

---

## 8. Deferred safety work

Recorded here so it is not forgotten, explicitly out of V0 scope:

- Test-section **interlock** switch that forces `FAULTED` when the enclosure opens (V1).
- Independent hardware over-current trip on the fan supply beyond the fuse (V1).
- A separate `docs/safety-laser.md` with interlocks and controlled access **before any PIV
  work begins** (V4). Nothing in the PIV milestone may start until that document exists.
- Fog fluid handling and ventilation requirements (V3).
