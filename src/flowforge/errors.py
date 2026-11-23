"""Catchable application failures, separate from programming errors.

Later subsystems may derive more specific failures; this is not the experiment
engine's failure-reason enum or a hardware safety mechanism.
"""


class FlowForgeError(Exception):
    """Base for expected FlowForge application failures."""


class ConfigurationError(FlowForgeError):
    """A request or configuration cannot be used as supplied."""
