from dataclasses import FrozenInstanceError
from itertools import product

import pytest

from flowforge.provenance import Provenance, derived_provenance
from flowforge.quantity import Quantity


@pytest.mark.parametrize("source", list(Provenance))
def test_every_documented_tag_propagates(source: Provenance) -> None:
    expected = (
        Provenance.ESTIMATED
        if source in {Provenance.ASSUMED, Provenance.ESTIMATED}
        else Provenance.DERIVED
    )
    assert derived_provenance([source]) is expected


@pytest.mark.parametrize("sources", list(product(Provenance, repeat=2)))
def test_mixed_sources_never_hide_assumptions(sources: tuple[Provenance, ...]) -> None:
    expected = (
        Provenance.ESTIMATED
        if any(source in {Provenance.ASSUMED, Provenance.ESTIMATED} for source in sources)
        else Provenance.DERIVED
    )
    assert derived_provenance(sources) is expected


def test_model_estimates_and_missing_sources_are_explicit() -> None:
    assert derived_provenance([Provenance.MEASURED], estimated=True) is Provenance.ESTIMATED
    with pytest.raises(ValueError):
        derived_provenance([])
    with pytest.raises(TypeError):
        derived_provenance(["MEASURED"])  # type: ignore[list-item]


@pytest.mark.parametrize(
    ("value", "u", "expected"),
    [
        (0.4712, 0.0937, "0.471 ± 0.094"),
        (0.173829, 0.0021, "0.1738 ± 0.0021"),
        (1.234, 0.0996, "1.23 ± 0.10"),
        (-0.4712, 0.0937, "-0.471 ± 0.094"),
        (0.125, 0.0, "0.125 ± 0"),
    ],
)
def test_numeric_reporting_matches_measurement_model(value: float, u: float, expected: str) -> None:
    result = str(Quantity(value, u, "N", Provenance.MEASURED))
    assert result == expected + " N [MEASURED]"


def test_standard_uncertainty_and_expansion_are_distinct() -> None:
    q = Quantity(0.4712, 0.0937, "", Provenance.DERIVED, coverage_factor=2)
    assert str(q) == "0.47 ± 0.19 [DERIVED] (k=2)"
    # Resolution uses three standard uncertainties, not three expanded intervals.
    assert "not resolved" not in str(Quantity(0.08, 0.02, "N", Provenance.MEASURED, 3))


def test_unknown_uncertainty_and_low_signal_are_loud() -> None:
    assert str(Quantity(1.0, None, "Pa", Provenance.MEASURED)) == (
        "1.0 Pa [MEASURED] — uncertainty not established"
    )
    assert "< 3σ — not resolved" in str(Quantity(0.01, 0.02, "N", Provenance.MEASURED))
    assert "not resolved" not in str(Quantity(0.06, 0.02, "N", Provenance.MEASURED))


@pytest.mark.parametrize(
    ("value", "u"),
    [
        (float("nan"), 1.0),
        (float("inf"), 1.0),
        (1.0, float("nan")),
        (1.0, float("inf")),
        (1.0, -0.1),
    ],
)
def test_invalid_numbers_are_rejected(value: float, u: float) -> None:
    with pytest.raises(ValueError):
        Quantity(value, u, "N", Provenance.MEASURED)


@pytest.mark.parametrize("factor", [0, -1, 2.0, True])
def test_invalid_coverage_factor_is_rejected(factor: int) -> None:
    with pytest.raises(ValueError):
        Quantity(1.0, 0.1, "N", Provenance.MEASURED, factor)


def test_quantity_is_immutable_and_derived_constructor_preserves_inputs() -> None:
    force = Quantity(0.5, 0.01, "N", Provenance.MEASURED)
    area = Quantity(0.01, None, "m²", Provenance.ASSUMED)
    result = Quantity.derived(
        50.0,
        None,
        "Pa",
        inputs={"force": force, "area": area},
        formula="F/A",
        method="fixture calculation",
    )
    assert result.provenance is Provenance.ESTIMATED
    assert result.inputs == ("force", "area")
    assert result.formula == "F/A"
    assert result.method == "fixture calculation"
    assert "uncertainty not established" in str(result)
    with pytest.raises(FrozenInstanceError):
        result.value = 4.0  # type: ignore[misc]


def test_resolution_boundary_uses_standard_decimal_uncertainty() -> None:
    assert "not resolved" not in str(Quantity(0.3, 0.1, "N", Provenance.MEASURED))
    assert "not resolved" in str(Quantity(0.299, 0.1, "N", Provenance.MEASURED))


@pytest.mark.parametrize(("value", "u"), [(1e100, 1e-100), (1e-200, 1e-210)])
def test_formatter_handles_finite_scale_separation(value: float, u: float) -> None:
    from decimal import Decimal

    rendered = str(Quantity(value, u, "", Provenance.DERIVED))
    number, remainder = rendered.split(" ± ")
    uncertainty = remainder.split(" [")[0]
    assert Decimal(number) == Decimal(str(value))
    assert Decimal(uncertainty) == Decimal(str(u))
