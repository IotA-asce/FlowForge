"""Explicit human/JSON logging sinks. Importing this module configures nothing."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import TextIO

JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


class JsonFormatter(logging.Formatter):
    """One strict JSON object per record, including escaped exception text."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "fields": json.loads(getattr(record, "flowforge_fields_json", "{}")),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, allow_nan=False)


class _OwnedHandler(logging.StreamHandler[TextIO]):
    """Identify only the handlers managed by this module."""


def close_logging() -> None:
    """Detach/close our handlers without closing caller streams or foreign handlers.

    Logger level and propagation settings are left configured. Call only while
    producers are stopped; configuration changes are not an atomic live switch.
    """
    logger = logging.getLogger("flowforge")
    for handler in logger.handlers[:]:
        if isinstance(handler, _OwnedHandler):
            logger.removeHandler(handler)
            handler.close()


def configure_logging(events: TextIO, *, console: TextIO | None = None) -> logging.Logger:
    """Configure flowforge and its children, leaving the root logger untouched.

    The caller owns both streams and their lifecycle. Future run storage can
    supply raw/events.jsonl; this helper never creates or opens a run directory.
    Repeated calls replace our sinks, preserving unrelated handlers. Call before
    starting producers. Individual raw samples must not be emitted as INFO events.
    """
    human = _OwnedHandler(sys.stderr if console is None else console)
    human.setLevel(logging.INFO)
    human.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    machine = _OwnedHandler(events)
    machine.setLevel(logging.DEBUG)
    machine.setFormatter(JsonFormatter())
    close_logging()
    logger = logging.getLogger("flowforge")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(human)
    logger.addHandler(machine)
    return logger


def log_event(
    logger: logging.Logger, event: str, /, *, level: int = logging.INFO, **fields: JsonValue
) -> None:
    """Emit a named event with fields nested separately from record metadata.

    Validate/freeze the fields before handing off to logging: nonfinite floats,
    cycles and unsupported objects fail synchronously without a partial write.
    This does not redact secrets or validate scientific measurement payloads.
    """
    fields_json = json.dumps(fields, ensure_ascii=False, allow_nan=False)
    logger.log(level, event, extra={"flowforge_fields_json": fields_json})
