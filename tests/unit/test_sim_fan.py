import pytest

from flowforge.devices.sim.fan import fan_speed_after


def test_spin_up_matches_one_time_constant():
    speed = fan_speed_after(0.0, 0.7, 1.5, slope_m_s=10.0, stall_duty=0.2)
    assert speed == pytest.approx(3.1606027941427883)


@pytest.mark.parametrize("duty", [0.0, 0.2])
def test_at_or_below_stall_the_fan_spins_down(duty):
    speed = fan_speed_after(5.0, duty, 1.5, slope_m_s=10.0, stall_duty=0.2)
    assert speed == pytest.approx(1.8393972058572117)


def test_zero_duration_preserves_speed_and_split_advance_matches_one_interval():
    model = {"slope_m_s": 8.0, "stall_duty": 0.25}
    assert fan_speed_after(1.25, 0.75, 0.0, **model) == 1.25
    midpoint = fan_speed_after(1.25, 0.75, 1.0, **model)
    assert fan_speed_after(midpoint, 0.75, 2.0, **model) == pytest.approx(
        fan_speed_after(1.25, 0.75, 3.0, **model)
    )
    assert fan_speed_after(1.25, 0.75, 600.0, **model) == pytest.approx(4.0)


@pytest.mark.parametrize(
    "override",
    [
        {"speed_m_s": -1.0},
        {"duty": 1.01},
        {"elapsed_s": -0.1},
        {"slope_m_s": 0.0},
        {"stall_duty": -0.1},
        {"time_constant_s": 0.0},
        {"elapsed_s": float("nan")},
        {"slope_m_s": float("inf")},
    ],
)
def test_invalid_model_inputs_are_rejected(override):
    args = {
        "speed_m_s": 1.0,
        "duty": 0.5,
        "elapsed_s": 1.0,
        "slope_m_s": 10.0,
        "stall_duty": 0.2,
        "time_constant_s": 1.5,
    }
    with pytest.raises(ValueError):
        fan_speed_after(**(args | override))
