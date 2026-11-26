"""Simulated fan airspeed under a constant duty command."""

import math


def fan_speed_after(
    speed_m_s: float,
    duty: float,
    elapsed_s: float,
    *,
    slope_m_s: float,
    stall_duty: float,
    time_constant_s: float = 1.5,
) -> float:
    """Return modeled airspeed after a constant-duty interval.

    Duty and stall duty are fractions in [0, 1]. Slope is the target airspeed
    gain per unit duty above stall. The closed-form lag allows irregular
    virtual time steps without a numerical integration step size.
    """
    if not all(
        math.isfinite(value)
        for value in (speed_m_s, duty, elapsed_s, slope_m_s, stall_duty, time_constant_s)
    ):
        raise ValueError("fan model inputs must be finite")
    if not 0 <= duty <= 1 or not 0 <= stall_duty <= 1:
        raise ValueError("duty and stall duty must be between zero and one")
    if speed_m_s < 0 or elapsed_s < 0 or slope_m_s <= 0 or time_constant_s <= 0:
        raise ValueError(
            "speed and elapsed time must be nonnegative; slope and time constant positive"
        )

    target_m_s = slope_m_s * max(0.0, duty - stall_duty)
    exponent = -elapsed_s / time_constant_s
    remaining = math.exp(exponent)
    response = -math.expm1(exponent)
    return speed_m_s * remaining + target_m_s * response
