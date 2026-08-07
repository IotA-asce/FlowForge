# ADR-0004 — Host↔device protocol is NDJSON over USB CDC

**Status:** Accepted · 2026-08-07

## Context

Host and device exchange commands, acknowledgements, telemetry, events, and logs. Sustained
telemetry is roughly 5 kB/s ([device-protocol.md §5.4](../device-protocol.md#54-rate-budget)),
comfortably inside a USB CDC link's capability.

Debugging an instrument that produces wrong numbers means staring at what the device actually
said, often at 1 a.m., often on someone else's machine.

## Decision

Newline-delimited JSON over USB CDC. One object per line, UTF-8, 512-byte line limit. Samples
are batched per channel with a `t0`/`dt` pair rather than a timestamp per sample.

Unknown fields and unknown message types are ignored by both sides; only the major version `v`
gates compatibility.

## Alternatives considered

**Custom binary frames** (length + type + payload + CRC). Perhaps 4× smaller and marginally
cheaper to parse. Rejected: the bandwidth saving is irrelevant at 0.5 % link utilisation, and it
costs a decoder on both sides, a hex dump instead of readable text, and a much harder time for
anyone reimplementing the device. Framing robustness — the usual argument for length-prefixing —
is fully served here by the fact that JSON cannot contain a raw newline, so line-splitting is a
correct framing primitive.

**Protobuf / CBOR / MessagePack.** Schema discipline and compactness, at the cost of a code
generation step, a schema-version dance, and losing `cat /dev/tty*` as a debugging tool. Would
be the right answer at 100× the data rate.

**SCPI / text command language.** Familiar to instrument people, but no natural structure for
batched multi-channel telemetry, and every implementation invents its own parsing quirks.

**Firmware exposing a filesystem or REST API.** Far more machinery than a point-to-point USB
link needs.

## Consequences

**Good**

- The instrument is directly readable: connect a terminal and watch it work.
- Adding a channel, a command, or a status bit is additive and needs no version bump.
- Both codecs are testable against a shared corpus of literal message strings, which catches
  divergence between the C++ and Python implementations at build time.

**Bad, and accepted**

- JSON parsing on the MCU needs a fixed-capacity, allocation-free parser (ArduinoJson with a
  static document) to avoid heap fragmentation in a long run. This is a firmware constraint,
  written down here so it is not rediscovered.
- Floats in JSON are decimal text: encoding must emit enough digits to round-trip, which is why
  force is transported as **integer counts** and the SI value is explicitly advisory
  ([ADR-0009](0009-store-raw-counts-alongside-si.md)).
- Batching means a sample's timestamp is `t0 + i·dt`, so intra-batch jitter is not represented.
  Acceptable because acquisition is DRDY-driven and the jitter is far below the noise floor; a
  non-uniform batch falls back to an explicit `ts` array.
- Migrating to a binary format later is a major version bump. The `Transport` interface makes
  that a contained change, and 0.5 % link utilisation means it is unlikely to be forced.
