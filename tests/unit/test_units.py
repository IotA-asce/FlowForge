"""Unit conversions are mathematical fixtures, not calibrated measurements."""

import pytest

from flowforge.units import (
    celsius_to_kelvin,
    fraction_to_percent,
    g_to_kg,
    kelvin_to_celsius,
    kg_to_g,
    m_to_mm,
    mm_to_m,
    percent_to_fraction,
)

PAIRS = (
    (mm_to_m, m_to_mm),
    (g_to_kg, kg_to_g),
    (percent_to_fraction, fraction_to_percent),
    (celsius_to_kelvin, kelvin_to_celsius),
)
ALL = tuple(function for pair in PAIRS for function in pair)


@pytest.mark.parametrize(
    "function,value,expected",
    [
        (mm_to_m, 25, 0.025),
        (m_to_mm, 0.1, 100),
        (g_to_kg, 250, 0.25),
        (kg_to_g, 0.25, 250),
        (percent_to_fraction, 4.9, 0.049),
        (fraction_to_percent, 0.0625, 6.25),
        (celsius_to_kelvin, 20, 293.15),
        (kelvin_to_celsius, 293.15, 20),
        (celsius_to_kelvin, -273.15, 0),
        (kelvin_to_celsius, 0, -273.15),
        (mm_to_m, -25, -0.025),
        (g_to_kg, -250, -0.25),
        (percent_to_fraction, 150, 1.5),
        (fraction_to_percent, -0.5, -50),
    ],
)
def test_reference_values(function, value, expected):
    assert function(value) == pytest.approx(expected)


@pytest.mark.parametrize("forward,reverse", PAIRS)
@pytest.mark.parametrize("value", [0, 0.001, 25, 1000])
def test_round_trip(forward, reverse, value):
    assert reverse(forward(value)) == pytest.approx(value, abs=1e-10)


@pytest.mark.parametrize("function", ALL)
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), 10**1000])
def test_nonfinite_and_unrepresentable_input_rejected(function, value):
    with pytest.raises(ValueError, match="finite"):
        function(value)


@pytest.mark.parametrize("function", ALL)
@pytest.mark.parametrize("value", [True, False, "25", None])
def test_invalid_types_rejected(function, value):
    with pytest.raises(TypeError, match="number"):
        function(value)


@pytest.mark.parametrize(
    "function,value", [(celsius_to_kelvin, -273.151), (kelvin_to_celsius, -0.001)]
)
def test_temperature_below_absolute_zero_rejected(function, value):
    with pytest.raises(ValueError, match="absolute zero"):
        function(value)


@pytest.mark.parametrize("function", [m_to_mm, kg_to_g, fraction_to_percent])
def test_result_overflow_is_not_reported_as_infinity(function):
    with pytest.raises(ValueError, match="finite"):
        function(1e308)
