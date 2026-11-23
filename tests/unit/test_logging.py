"""Observable sink, exception and lifecycle contracts; no instrument or run files."""

import io
import json
import logging
import subprocess
import sys

import pytest

from flowforge.errors import ConfigurationError, FlowForgeError
from flowforge.logging import JsonFormatter, close_logging, configure_logging, log_event


@pytest.fixture(autouse=True)
def isolated_logger():
    logger = logging.getLogger("flowforge")
    handlers, level, propagate = logger.handlers[:], logger.level, logger.propagate
    logger.handlers = []
    yield
    close_logging()
    logger.handlers, logger.level, logger.propagate = handlers, level, propagate


def test_import_does_not_configure_logging():
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import logging
root = logging.getLogger()
handler = logging.NullHandler()
root.addHandler(handler)
logger = logging.getLogger('flowforge')
before = (root.handlers[:], root.level, logger.handlers[:], logger.level, logger.propagate)
import flowforge.logging
import flowforge.errors
after = (root.handlers[:], root.level, logger.handlers[:], logger.level, logger.propagate)
assert before == after
""",
        ],
        check=True,
    )


def test_two_sinks_preserve_fields_and_filter_debug():
    events, console = io.StringIO(), io.StringIO()
    root = logging.getLogger()
    before = root.handlers[:], root.level
    logger = configure_logging(events, console=console)
    log_event(logger, "connected\nready", device={"id": "fixture", "channels": [1, 2]})
    log_event(logger, "diagnostic", level=logging.DEBUG, event="nested key", timestamp=7)
    rows = [json.loads(line) for line in events.getvalue().splitlines()]
    assert len(rows) == 2
    assert rows[0]["event"] == "connected\nready"
    assert rows[0]["fields"] == {"device": {"id": "fixture", "channels": [1, 2]}}
    assert rows[0]["timestamp"].endswith("+00:00")
    assert rows[0]["logger"] == "flowforge"
    assert rows[1]["level"] == "DEBUG"
    assert rows[1]["fields"] == {"event": "nested key", "timestamp": 7}
    assert "connected" in console.getvalue()
    assert "diagnostic" not in console.getvalue()
    assert (root.handlers[:], root.level) == before


def test_exception_is_one_json_line_and_error_is_catchable():
    events, console = io.StringIO(), io.StringIO()
    logger = configure_logging(events, console=console)
    with pytest.raises(FlowForgeError):
        raise ConfigurationError("invalid request")
    try:
        raise ConfigurationError("invalid\nrequest")
    except FlowForgeError:
        logger.exception("validation failed")
    lines = events.getvalue().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["fields"] == {}
    assert row["level"] == "ERROR"
    assert "ConfigurationError" in row["exception"]
    assert "invalid\nrequest" in row["exception"]
    assert "Traceback" in console.getvalue()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), object()])
def test_invalid_json_fails_before_any_sink_write(value):
    events, console = io.StringIO(), io.StringIO()
    logger = configure_logging(events, console=console)
    with pytest.raises((ValueError, TypeError)):
        log_event(logger, "bad field", value=value)
    assert events.getvalue() == console.getvalue() == ""


def test_repeat_configuration_and_close_preserve_foreign_handlers_and_streams():
    events, console, old_events = io.StringIO(), io.StringIO(), io.StringIO()
    foreign_stream = io.StringIO()
    foreign = logging.StreamHandler(foreign_stream)
    logger = logging.getLogger("flowforge")
    logger.addHandler(foreign)
    configure_logging(old_events, console=console)
    configure_logging(events, console=console)
    log_event(logger.getChild("fixture"), "once", count=1)
    assert old_events.getvalue() == ""
    assert len(events.getvalue().splitlines()) == 1
    assert len(console.getvalue().splitlines()) == 1
    assert foreign_stream.getvalue() == "once\n"
    close_logging()
    close_logging()
    assert logger.handlers == [foreign]
    for stream in [events, console, old_events, foreign_stream]:
        assert not stream.closed
        stream.write("still open")


def test_fields_are_frozen_before_a_delayed_handler_formats_them():
    records = []

    class DelayedHandler(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = configure_logging(io.StringIO(), console=io.StringIO())
    logger.addHandler(DelayedHandler())
    fields = {"counts": [1, 2]}
    log_event(logger, "snapshot", details=fields)
    fields["counts"].append(3)
    row = json.loads(JsonFormatter().format(records[0]))
    assert row["fields"] == {"details": {"counts": [1, 2]}}
    cyclic = []
    cyclic.append(cyclic)
    with pytest.raises(ValueError, match="Circular"):
        log_event(logger, "cyclic", values=cyclic)
    assert len(records) == 1


def test_console_defaults_to_current_stderr(monkeypatch):
    console = io.StringIO()
    monkeypatch.setattr(sys, "stderr", console)
    logger = configure_logging(io.StringIO())
    logger.info("ready %s", "fixture")
    assert console.getvalue() == "INFO ready fixture\n"
