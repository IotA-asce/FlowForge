# ADR-0003 — Firmware on ESP32-S3 via PlatformIO/Arduino over FreeRTOS, with a HAL seam

**Status:** Accepted · 2026-08-07

## Context

Something must sample a load-cell ADC at 80+ Hz with accurate timestamps, read two I²C sensors,
count tachometer edges, drive a 25 kHz PWM, enforce a 500 ms heartbeat watchdog, and stream
telemetry — all with timing that does not depend on a general-purpose OS's scheduler.

The requirements also say not to hard-code FlowForge to exact hardware.

## Decision

**ESP32-S3**, developed with **PlatformIO** using the **Arduino-ESP32** framework, which exposes
the underlying **FreeRTOS** directly.

Three tasks with explicit priorities and core pinning:

| Task | Core | Priority | Responsibility |
| --- | --- | --- | --- |
| acquisition | 1 | high | DRDY-driven sensor reads, timestamping, SPSC queue |
| control + safety | 0 | high | 100 Hz tick, watchdog, ramp limiting, fault latch, PWM |
| comms | 0 | normal | NDJSON encode/decode, USB CDC |

Source is split so that portability is structural, not aspirational:

- `proto/` — message encode/decode. No hardware includes. Compiles and tests natively.
- `safety/` — watchdog, limits, fault latch. No hardware includes. Compiles and tests natively.
- `control/` — duty state machine and ramp limiting.
- `hal/` — one file per device: `board.h` pinmap, `adc_nau7802.cpp`, `dp_sdp8xx.cpp`,
  `env_bme280.cpp`, `fan_ledc.cpp`.

Swapping the load-cell ADC is one file in `hal/` plus a changed channel descriptor in the
`hello` message. Porting to a different MCU is `hal/` plus the FreeRTOS setup.

## Alternatives considered

**Bare-metal / superloop.** Simpler to reason about, but interleaving a 500 ms safety watchdog,
DRDY-driven ADC reads, and blocking USB writes in one loop reliably produces the bug where a
slow serial write delays the safety tick. Task priorities are exactly the tool for this.

**ESP-IDF directly.** More control, better long-term ergonomics, no Arduino abstraction. Costs
a steeper contributor ramp for a project whose contributors are hobbyist aerodynamicists.
Arduino-ESP32 *is* ESP-IDF underneath and the FreeRTOS API is fully available, so nothing is
foreclosed; if IDF becomes necessary, `proto/` and `safety/` port unchanged.

**RP2040.** Cheaper, PIO is excellent for tachometer capture, and its dual cores are simpler.
Rejected mainly for the weaker path to Wi-Fi later (V3+ camera synchronisation) and a smaller
selection of ready sensor drivers. The HAL seam means this is reversible.

**STM32.** Best timing peripherals of the three, worst accessibility for the target audience.

**Raspberry Pi doing everything, no MCU.** Attractive for the camera milestones, but Linux
cannot guarantee the microsecond-scale timestamping the measurement model relies on, and the
safety watchdog would then depend on the same machine running the experiment — the exact
coupling [safety.md](../safety.md) exists to avoid.

## Consequences

**Good**

- The safety watchdog runs at high priority on a core that is not doing serial I/O.
- `proto/` and `safety/` are unit-tested in CI with **no board attached** (`pio test -e native`),
  and `proto/` is tested against the *same* golden message corpus as the host codec.
- Native USB CDC gives high throughput and a DTR line usable as a disconnect signal (SR-3).

**Bad, and accepted**

- Arduino-ESP32 pulls in abstractions with occasionally surprising timing. Anything
  timing-critical uses `esp_timer` and FreeRTOS primitives directly, never `delay()`/`millis()`.
- On some ESP32 boards asserting DTR resets the MCU. This is *desirable* for safety but means a
  host connect may reset the device; the host handles the unsolicited `hello` and records
  `boot_count`, so a reset is visible rather than mysterious.
- Two languages in the project. Mitigated by keeping the firmware genuinely small and pushing
  every non-real-time decision to the host.
