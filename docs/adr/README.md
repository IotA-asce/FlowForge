# Architecture Decision Records

Decisions that needed justification, and the alternatives they beat. Format: context →
decision → alternatives → consequences, including the bad ones.

An ADR is written when reversing the decision later would be expensive, or when a reader would
otherwise reasonably ask "why not the obvious thing?".

| # | Decision | Status |
| --- | --- | --- |
| [0001](0001-host-language-python.md) | Host application is Python 3.11+, managed with `uv` | Accepted |
| [0002](0002-single-python-package.md) | One installable Python package, not a multi-package monorepo | Accepted |
| [0003](0003-firmware-esp32-freertos.md) | Firmware on ESP32-S3 via PlatformIO/Arduino over FreeRTOS, with a HAL seam | Accepted |
| [0004](0004-ndjson-over-usb-serial.md) | Host↔device protocol is NDJSON over USB CDC | Accepted |
| [0005](0005-timebase-and-synchronisation.md) | The device's monotonic clock is the measurement timebase | Accepted |
| [0006](0006-run-directory-csv-json.md) | Experiments are directories of CSV + JSON, not a database | Accepted |
| [0007](0007-device-abstraction-via-protocols.md) | Device abstraction via structural `Protocol`s, no plugin framework | Accepted |
| [0008](0008-experiment-state-machine.md) | Experiments are an explicit state machine with a universal abort path | Accepted |
| [0009](0009-store-raw-counts-alongside-si.md) | Raw ADC counts are stored; calibration is applied only on the host | Accepted |
| [0010](0010-simulator-design.md) | Two-level simulator: in-process instrument and wire-level transport | Accepted |
| [0011](0011-open-loop-fan-control.md) | Open-loop fan duty with measured-speed reporting; no PID in V0 | Accepted |
| [0012](0012-uncertainty-and-provenance-types.md) | Uncertainty and provenance are types, not conventions | Accepted |
