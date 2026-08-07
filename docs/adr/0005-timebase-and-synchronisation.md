# ADR-0005 — The device's monotonic clock is the measurement timebase

**Status:** Accepted · 2026-08-07

## Context

Force samples at 80 Hz, differential pressure at 50 Hz, and environment at 1 Hz must be
combined into a single per-test-point result. Later milestones add camera frames, a second
force axis, and an angle encoder, all of which must align to the same timeline.

Between the sensor and the host sit: an I²C transaction, a queue, a JSON encoder, USB frame
scheduling (1 ms granularity), OS serial buffering, the Python GIL, and possibly a GC pause.
Aggregate jitter is tens of milliseconds and is neither constant nor symmetric.

At 15 m/s, 10 ms of flow travels 150 mm — more than the length of the test section.

## Decision

**Every sample is timestamped by the firmware** with `esp_timer_get_time()`, a monotonic
microsecond counter, and that timestamp — `t_dev` — is the only timebase used in analysis.

The host additionally maintains a `t_dev → t_host` mapping for human reference:

1. 1 Hz `ping`/`ack`, recording `(t_send_host, t_dev, t_recv_host)`.
2. Discard exchanges whose round-trip time is in the slowest quartile of a rolling window —
   those carry the most asymmetric delay.
3. Fit `t_host ≈ α·t_dev + β` by Theil–Sen regression, robust to the remaining outliers.
4. Write the fit, its residual MAD, **and every raw ping exchange** to `raw/clocksync.jsonl`.

Nothing downstream of acquisition consumes host time.

## Alternatives considered

**Host receive-time as the timebase.** Simplest, and wrong. It bakes tens of milliseconds of
non-stationary jitter into a measurement whose point is precision, and the error would be
invisible — it produces smooth, plausible, wrong data.

**Host timestamps corrected by an estimated constant latency.** Better, but the latency is not
constant; USB scheduling and OS buffering vary with system load, which is itself correlated
with what the host is doing during the run.

**NTP/PTP-style synchronisation on the device.** Overkill for a point-to-point USB link, and
would require the device to hold a wall-clock it has no other reason to have.

**A hardware sync pulse shared between MCU and camera (V3+).** Genuinely the right answer for
frame-accurate camera alignment, and this decision does not preclude it — the pulse would be
timestamped on `t_dev` like everything else. It is deferred because there is no camera yet.

## Consequences

**Good**

- Multi-rate channels align exactly; combining an 80 Hz force sample with a 1 Hz environment
  sample is interpolation on a clean axis, not guesswork.
- Host performance problems degrade *throughput*, never *accuracy*. A GC pause shows up as a
  dropout, which is counted and reported, rather than as a silent timing error.
- Camera and second-axis alignment in V1–V4 become lookups on an existing axis.

**Bad, and accepted**

- `t_dev` resets to zero on every device reboot. Runs are therefore bounded by a device session;
  a mid-run reboot is a fatal experiment error (correctly — `boot_count` changes and the host
  aborts) rather than a silently discontinuous timeline.
- Relating a run to wall-clock — "what was the room temperature at 14:25?" — requires the clock
  model. It is stored, so this is a lookup, but it is not free.
- The crystal drifts (tens of ppm). Over a 10-minute run that is a few milliseconds of absolute
  error against wall time and **zero** relative error within the run, which is the quantity the
  measurement depends on. `α` captures it anyway.
