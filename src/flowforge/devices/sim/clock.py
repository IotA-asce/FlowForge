"""Virtual device time for in-process simulation."""

from typing import final


@final
class VirtualClock:
    """Monotonic integer microseconds driven explicitly by the simulator."""

    def __init__(self, *, start_us: int = 0) -> None:
        self._time_us = self._checked_us(start_us, "start_us")

    @property
    def time_us(self) -> int:
        """Return the current device timestamp in microseconds."""
        return self._time_us

    def advance(self, elapsed_us: int) -> int:
        """Advance by a nonnegative duration and return the new timestamp."""
        self._time_us += self._checked_us(elapsed_us, "elapsed_us")
        return self._time_us

    @staticmethod
    def _checked_us(value: int, name: str) -> int:
        if type(value) is not int:
            raise TypeError(f"{name} must be an integer number of microseconds")
        if value < 0:
            raise ValueError(f"{name} must be nonnegative")
        return value
