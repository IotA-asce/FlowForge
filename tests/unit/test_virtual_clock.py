import pytest

from flowforge.devices.sim.clock import VirtualClock


def test_independent_clocks_replay_exact_device_timestamps():
    first = VirtualClock(start_us=9_007_199_254_740_992)
    second = VirtualClock(start_us=first.time_us)
    intervals = (1, 0, 19, 600_000_000)
    expected = [
        9_007_199_254_740_993,
        9_007_199_254_740_993,
        9_007_199_254_741_012,
        9_007_199_854_741_012,
    ]
    assert [first.advance(step) for step in intervals] == expected
    assert second.time_us == 9_007_199_254_740_992
    assert [second.advance(step) for step in intervals] == expected


@pytest.mark.parametrize(
    ("value", "error"), [(-1, ValueError), (1.5, TypeError), (True, TypeError)]
)
def test_invalid_microseconds_leave_clock_unchanged(value, error):
    with pytest.raises(error):
        VirtualClock(start_us=value)
    clock = VirtualClock()
    with pytest.raises(error):
        clock.advance(value)
    assert clock.time_us == 0
