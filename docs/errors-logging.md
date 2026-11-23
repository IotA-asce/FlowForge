# Errors and structured logging

The M0 leaves use only the Python standard library. Importing either module does
not configure logging, open files, start threads or touch devices.

## Errors

`FlowForgeError` is the base for expected application failures;
`ConfigurationError` specializes unusable requests/configuration. Catch these at
application boundaries; ordinary programming exceptions remain ordinary errors.
These types are not the later experiment failure-reason enum, configuration
validator or hardware abort mechanism. Existing Quantity/unit validation continues
to raise its documented ValueError/TypeError; it has not been silently converted.

## Explicit setup and ownership

```python
import io
import logging
from flowforge.logging import configure_logging, log_event, close_logging

# Tests use in-memory streams. Future run storage supplies raw/events.jsonl.
events = io.StringIO()
logger = configure_logging(events)  # human console defaults to current stderr
log_event(logger, "calibration.loaded", record_id="fixture-only")
log_event(logger, "diagnostic", level=logging.DEBUG, channel="force")
close_logging()
assert not events.closed
```

`configure_logging(events, console=...)` sets the named `flowforge` logger to DEBUG
with propagation disabled. Children use the same sinks unless explicitly
reconfigured by their caller. The root logger and unrelated application loggers
are untouched. Console receives INFO and above in human-readable form; events
receives DEBUG and above as one JSON object per line. Both thresholds are fixed
for this foundation. There is no automatic raw-sample logging or debug-samples CLI;
callers must not send individual samples to the console/INFO path.

Repeated configuration replaces only this module's handlers. Foreign handlers
remain installed and can have their own output policy. `close_logging()` detaches
and closes only owned handlers, leaves logger level/propagation configured, and
never closes the caller's streams. Callers own stream flushing/closing and must
stop producers before configuring/closing; setup is not an atomic live switch.
No run directories, event-file lifecycle, rotation, retention or durability claims
are provided here; those belong to acquisition/storage M2.

## Record contract

Records contain UTC ISO `timestamp`, `level`, `logger`, `event` and a `fields`
object. `log_event` accepts JSON-compatible fields (including nested lists/maps),
serializes them before emission and rejects nonfinite floats, cycles and unsupported
objects synchronously. A later mutation cannot alter an already queued record.
User keys are nested, so names such as event/timestamp cannot overwrite metadata.
Use string dictionary keys, as required by the typed API. No secret redaction or
scientific-value validation is performed; do not include credentials or treat
ordinary diagnostic floats as reported measurement Quantities.

Conventional stdlib calls are supported: `logger.info("ready %s", name)` and
`logger.exception("operation failed")`. Records from these calls have empty fields.
An exception includes escaped traceback text in the JSON `exception` property;
embedded newlines do not split machine records. The console keeps normal human
traceback formatting. Sink failures retain standard logging semantics; this is not
a lossless acquisition writer or a fault-safe hardware channel.

## Verification

Nine behavioral tests cover import isolation, root logger preservation, DEBUG
filtering, JSON escaping/nested metadata, exception traces, error catching,
nonfinite/unsupported/cyclic fields, field snapshots, repeated setup, child
logging, stderr selection and stream ownership. Together with existing tests:
175 tests. Strict mypy, Ruff, formatting, wheel/sdist build and a fresh-wheel smoke
are required. Ubuntu CI runs the same suite on Python 3.11/3.13.

This completes the M0 primitive implementation alongside existing quantities,
provenance, edge units and import-direction/CI checks. M1 simulator, acquisition,
run storage, calibration/uncertainty equations, engine, CLI and hardware remain
unimplemented milestones. A green foundation is not a working instrument.
