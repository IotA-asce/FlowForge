"""Explicit config/display conversions; internal values remain SI.

These functions convert scalar values, not Quantity or standard uncertainties.
They do not establish physical accuracy or validate channel-specific limits.
"""

from math import isfinite


def _finite(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("Conversion requires a real number")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError("Conversion requires a finite float") from error
    if not isfinite(result):
        raise ValueError("Conversion requires a finite float")
    return result


def mm_to_m(value: float) -> float:
    """Convert millimetres to metres; signed displacements are allowed."""
    return _finite(value) / 1000.0


def m_to_mm(value: float) -> float:
    """Convert metres to millimetres for display."""
    return _finite(_finite(value) * 1000.0)


def g_to_kg(value: float) -> float:
    """Convert grams to kilograms; signed differences are allowed."""
    return _finite(value) / 1000.0


def kg_to_g(value: float) -> float:
    """Convert kilograms to grams for display."""
    return _finite(_finite(value) * 1000.0)


def percent_to_fraction(value: float) -> float:
    """Convert percentage points to a fraction, without channel range checks."""
    return _finite(value) / 100.0


def fraction_to_percent(value: float) -> float:
    """Convert a fraction to percentage points for display."""
    return _finite(_finite(value) * 100.0)


def celsius_to_kelvin(value: float) -> float:
    """Convert absolute Celsius temperature to kelvin, not a temperature delta."""
    value = _finite(value)
    if value < -273.15:
        raise ValueError("Temperature cannot be below absolute zero")
    return _finite(value + 273.15)


def kelvin_to_celsius(value: float) -> float:
    """Convert absolute kelvin temperature to Celsius for display."""
    value = _finite(value)
    if value < 0:
        raise ValueError("Temperature cannot be below absolute zero")
    return _finite(value - 273.15)
