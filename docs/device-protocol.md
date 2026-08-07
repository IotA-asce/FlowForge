# FlowForge Host ↔ Device Protocol

**Protocol version:** 1
**Transport (V0):** USB CDC-ACM virtual serial, 8N1, 921600 baud nominal
**Encoding:** newline-delimited JSON (NDJSON), UTF-8, one object per line

Rationale for JSON over a binary frame format is in
[ADR-0004](adr/0004-ndjson-over-usb-serial.md). Short version: at our data rate the overhead is
irrelevant, and being able to `cat /dev/tty.usbmodem*` and read the instrument is worth more
than the bytes.

---

## 1. Framing and robustness rules

- One message per line, terminated by `\n` (`0x0A`). `\r` is tolerated and stripped.
- Maximum line length **512 bytes**. A longer line is a protocol error.
- JSON never contains a literal newline, so line-splitting is a safe framing primitive.
- A line that fails to parse is **counted, logged, and discarded** by both sides. It is never
  fatal. The counter is exposed in `get_state` and lands in the run summary.
- Unknown top-level fields are ignored by both sides. Unknown *message types* are ignored with
  a logged warning. This is what makes forward-compatible additions cheap.
- The device emits a `\n` first thing after boot to flush any partial line.

---

## 2. Envelope

Every message is a flat JSON object with these common fields:

| Field | Type | Direction | Meaning |
| --- | --- | --- | --- |
| `v` | int | both | Protocol major version. Currently `1`. **Required.** |
| `type` | string | both | `cmd`, `ack`, `err`, `tlm`, `evt`, `log`, `hello` |
| `t` | int | dev→host | Device monotonic timestamp, **microseconds since boot** |
| `req` | int | both | Request id. Set by host on `cmd`; echoed on the matching `ack`/`err` |
| `seq` | int | dev→host | Per-stream monotonic counter, used for dropout detection |

`t` is a 64-bit integer from `esp_timer_get_time()`. It never jumps, never goes backwards, and
is **the measurement timebase**. Host wall-clock is never used for anything that ends up in an
analysis. See [ADR-0005](adr/0005-timebase-and-synchronisation.md).

---

## 3. Commands (host → device)

```json
{"v":1,"type":"cmd","req":17,"cmd":"set_fan","args":{"duty":0.62}}
```

| `cmd` | Args | Effect | Allowed when |
| --- | --- | --- | --- |
| `hello` | — | Identify. Device replies with a `hello` message. | always |
| `ping` | — | Device replies `ack` immediately with current `t`. Used for clock sync. | always |
| `get_state` | — | Full device state snapshot. | always |
| `arm` | — | Permit fan actuation. Requires heartbeat already flowing and no latched fault. | `IDLE` |
| `disarm` | — | Fan to zero, forbid actuation. | any |
| `set_fan` | `duty` 0.0–1.0 | Request fan duty. Subject to ceiling and ramp limiting. | `ARMED` |
| `stop` | — | Immediate duty 0. **Never refused, in any state.** | always |
| `heartbeat` | — | Resets the host-liveness watchdog. No `ack` is sent. | always |
| `stream` | `enable`, `channels[]`, `rates{}` | Configure telemetry. | always |
| `set_limits` | `max_duty`, `ramp_per_s` | Tighten limits. **Cannot loosen** past the compile-time ceiling. | `IDLE` |
| `clear_fault` | `fault` | Clear one latched fault. Never clears an active condition. | `FAULTED` |
| `selftest` | — | Read every sensor once, report per-channel health. | `IDLE` |
| `reset` | — | Software reset. Fan is stopped first. | always |

Rules:

- `set_fan` while disarmed returns `err` with `E_NOT_ARMED` and does **not** change duty.
- `stop` is idempotent, always accepted, and always acknowledged — including from `FAULTED`.
- There is deliberately no `tare` and no `calibrate` command. The device knows nothing about
  calibration; taring is host-side arithmetic over streamed counts.

### 3.1 `ack` / `err`

```json
{"v":1,"type":"ack","t":123456789,"req":17,"data":{"duty":0.62}}
{"v":1,"type":"err","t":123456789,"req":17,"code":"E_NOT_ARMED","msg":"fan actuation requires arm"}
```

Error codes (closed set):

| Code | Meaning |
| --- | --- |
| `E_PARSE` | Malformed JSON or oversize line |
| `E_UNKNOWN_CMD` | Unrecognised `cmd` |
| `E_BAD_ARGS` | Missing or out-of-range argument |
| `E_NOT_ARMED` | Actuation attempted while disarmed |
| `E_FAULTED` | Command refused because a fault is latched |
| `E_LIMIT` | Requested value exceeds a hard limit (clamped value is returned in `data`) |
| `E_SENSOR` | A required sensor is not responding |
| `E_BUSY` | Command cannot run in the current state |
| `E_VERSION` | Protocol major version mismatch |

### 3.2 Timeouts

The host waits **250 ms** for an `ack`/`err`. On timeout it retries once with the *same*
`req`; the device must treat a repeated `req` as idempotent for all commands except `reset`.
A second timeout escalates to `DEVICE_DISCONNECTED`, which aborts the experiment via the
`ABORTING` path.

---

## 4. `hello` (device → host)

Sent unsolicited on boot and in reply to the `hello` command.

```json
{"v":1,"type":"hello","t":1042,
 "device_id":"ff-esp32-0A1B2C",
 "fw_version":"0.3.1",
 "fw_git":"a1b2c3d",
 "proto":1,
 "board":"flowforge-ctrl-rev-a",
 "boot_count":41,
 "reset_reason":"POWERON",
 "limits":{"max_duty":0.95,"ramp_per_s":0.5,"heartbeat_timeout_ms":500},
 "channels":[
   {"name":"force.drag","kind":"force","unit":"count","hw":"NAU7802","rate_hz":80,"si_unit":"N","si_valid":false},
   {"name":"dp","kind":"differential_pressure","unit":"Pa","hw":"SDP810-500Pa","rate_hz":50,"si_unit":"Pa","si_valid":true},
   {"name":"env","kind":"environment","unit":"si","hw":"BME280","rate_hz":1,"si_unit":"","si_valid":true},
   {"name":"fan.tach","kind":"tachometer","unit":"Hz","hw":"pin34","rate_hz":10,"si_unit":"Hz","si_valid":true}
 ]}
```

The host **refuses to run an experiment** if `proto` major differs from what it supports, or if
a channel required by the experiment config is absent. `si_valid: false` on the force channel
is the explicit statement that the device's SI figure is a convenience only and that the host
must derive force from counts.

`device_id`, `fw_version`, `fw_git`, `board`, and `reset_reason` are all copied verbatim into
`metadata.json`. A run whose firmware version cannot be recorded is not a reproducible run.

---

## 5. Telemetry

Samples are **batched per channel** to cut per-message overhead. A batch is emitted when it
fills or after 100 ms, whichever comes first.

### 5.1 Uniformly sampled channel

```json
{"v":1,"type":"tlm","ch":"force.drag","seq":4412,
 "t0":123456789,"dt":12500,"n":8,
 "raw":[8421031,8421044,8420998,8421012,8421039,8421002,8421027,8421018],
 "si":[0.1731,0.1734,0.1725,0.1728,0.1734,0.1726,0.1732,0.1730],
 "st":0}
```

Sample `i` has timestamp `t0 + i·dt`. `dt` is the *nominal* interval; the acquisition task is
DRDY-driven, so `t0` is the true hardware timestamp of the first sample in the batch and jitter
within a batch is below the noise floor. If a batch is not uniform (a sample was late), the
device sends `ts` — an array of microsecond offsets from `t0` — instead of `dt`.

### 5.2 Non-uniform / composite channel

```json
{"v":1,"type":"tlm","ch":"env","seq":301,"t":123456789,
 "si":{"t_c":22.31,"p_pa":100812.4,"rh":0.412},"st":0}
```

### 5.3 Fields

| Field | Meaning |
| --- | --- |
| `ch` | Channel name, exactly as advertised in `hello` |
| `seq` | Per-channel monotonic batch counter. A gap means the device dropped a batch. |
| `raw` | Uncalibrated device units — ADC counts for the load cell. Present when meaningful. |
| `si` | Device's best-effort SI value. **Advisory.** Only trusted where `si_valid` is true. |
| `st` | Status bitfield, see below |

Status bits (`st`):

| Bit | Name | Meaning |
| --- | --- | --- |
| 0 | `SATURATED` | ADC at or near rail — the reading is not a measurement |
| 1 | `STALE` | Sensor did not produce new data; value repeated |
| 2 | `SENSOR_ERROR` | Bus error, CRC failure, or NACK |
| 3 | `RANGE` | Value outside the sensor's specified range |
| 4 | `WARMUP` | Sensor within its post-power-on settling period |

Any non-zero `st` propagates into `raw/samples.csv` and excludes the sample from aggregation
while remaining in the raw file. Samples are never silently dropped on the host.

### 5.4 Rate budget

| Channel | Rate | Batch | Msgs/s | ≈ bytes/s |
| --- | --- | --- | --- | --- |
| `force.drag` | 80 Hz | 8 | 10 | 2 800 |
| `dp` | 50 Hz | 5 | 10 | 1 400 |
| `env` | 1 Hz | 1 | 1 | 90 |
| `fan.tach` | 10 Hz | 10 | 1 | 150 |
| `evt`/`ack` | — | — | ~6 | 600 |

≈ **5 kB/s**, roughly 0.5 % of a conservative USB CDC budget. There is ample headroom for the
V1 lift channel and V2 angle feedback without changing the format.

---

## 6. Events and logs

```json
{"v":1,"type":"evt","t":123456789,"evt":"fault","fault":"HEARTBEAT_TIMEOUT","detail":{"last_hb_ms":712}}
{"v":1,"type":"evt","t":123456789,"evt":"state","from":"ARMED","to":"FAULTED"}
{"v":1,"type":"log","t":123456789,"lvl":"warn","msg":"SDP810 CRC retry","n":3}
```

Events are part of the experiment record and are written verbatim into `raw/events.jsonl`.
Device faults are `evt`, not `log`; the distinction is that an `evt` changes device behaviour
and a `log` does not.

---

## 7. Device state machine

```text
                 boot
                   │
                   ▼
             ┌──────────┐   selftest ok
             │  BOOTING │───────────────┐
             └──────────┘               ▼
                                    ┌───────┐  arm (hb flowing)   ┌───────┐
                                    │ IDLE  │────────────────────►│ ARMED │
                                    └───────┘◄────────────────────└───────┘
                                        ▲          disarm / stop      │
                          clear_fault    │                            │ fault
                                    ┌────┴─────┐◄──────────────────────┘
                                    │ FAULTED  │  duty forced 0, latched
                                    └──────────┘
```

Entry to `FAULTED` sets duty to zero within one control tick (10 ms) and latches. Exit requires
an explicit `clear_fault` naming the specific fault, and the underlying condition must have
cleared. **The device never re-enables the fan by itself, and never returns to `ARMED` without
a fresh `arm` command.** See [safety.md](safety.md).

Fault sources: `HEARTBEAT_TIMEOUT`, `USB_DISCONNECT` (DTR deasserted), `SENSOR_TIMEOUT`,
`OVER_TEMP`, `TACH_STALL` (duty commanded but tachometer reads zero), `WATCHDOG_RESET`,
`BROWNOUT`.

---

## 8. Session lifecycle

```text
host                                    device
 │  open port, assert DTR                │
 │  ────────────────────────────────────►│ (may reset on DTR, depends on board)
 │  ◄──────────── hello (unsolicited) ───│
 │  cmd hello  ─────────────────────────►│
 │  ◄─────────── hello ──────────────────│   version + channel check
 │  cmd stream {enable:true,...} ───────►│
 │  ◄─────────── ack ────────────────────│
 │  ◄─────────── tlm ... (continuous) ───│
 │  heartbeat @ 4 Hz ───────────────────►│   (no acks)
 │  ping @ 1 Hz ────────────────────────►│
 │  ◄─────────── ack {t} ────────────────│   clock model update
 │  cmd arm ────────────────────────────►│
 │  cmd set_fan {duty} ─────────────────►│
 │        ... experiment ...             │
 │  cmd stop ───────────────────────────►│
 │  cmd disarm ─────────────────────────►│
 │  close port / drop DTR                │   device faults to safe state anyway
```

The host sends `heartbeat` from a dedicated thread that does not share a lock with the
experiment engine, so a stalled analysis step cannot starve the watchdog into a spurious abort
— but a *hung host process* still trips it, which is exactly the intent.

---

## 9. Clock synchronisation

The host runs a 1 Hz `ping` exchange and records `(t_send_host, t_dev, t_recv_host)`.

1. Round-trip `rtt = t_recv_host − t_send_host`. Exchanges with `rtt` above the 25th percentile
   of a rolling window are discarded — they carry the most asymmetric delay.
2. The surviving pairs `(t_dev, t_send_host + rtt/2)` are fitted by Theil–Sen regression to
   `t_host ≈ α·t_dev + β`.
3. `α` captures crystal skew (typically 10–50 ppm), `β` the offset.
4. The fit, its residual MAD, and **every raw ping exchange** are written to
   `raw/clocksync.jsonl`.

Analysis uses `t_dev` exclusively. The model exists so a human — or, later, a camera pipeline —
can relate device time to wall time, and so that a bad mapping is detectable after the fact
rather than baked in.

---

## 10. Versioning policy

- `v` is the **major** version. Incompatible changes bump it, and the host refuses to run.
- Additive changes — new channels, new commands, new optional fields, new status bits — do
  **not** bump `v`. Both sides ignore what they do not recognise.
- `hello.fw_version` is the firmware semantic version and is recorded in every run.
- The wire format is frozen by golden-file tests in `tests/unit/test_protocol_codec.py`: a
  corpus of literal message strings that must round-trip. Changing the format means changing
  those files deliberately.

---

## 11. Non-goals for V0

No Wi-Fi, BLE, TCP, mDNS discovery, encryption, authentication, or multi-device addressing.
`device_id` exists so that recorded data is attributable, not so that a bus can be arbitrated.
The transport is abstracted behind a `Transport` interface with `read_line`/`write_line`, so
adding a socket transport later is a new class, not a protocol change.
