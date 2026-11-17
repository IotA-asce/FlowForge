"""Immutable reportable quantities; no device access or implicit arithmetic."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext
from math import isfinite

from flowforge.provenance import Provenance, derived_provenance


@dataclass(frozen=True)
class Quantity:
    value: float
    u: float | None
    unit: str
    provenance: Provenance
    coverage_factor: int = 1
    formula: str | None = None
    method: str | None = None
    inputs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isfinite(self.value):
            raise ValueError("Quantity value must be finite")
        if self.u is not None and (not isfinite(self.u) or self.u < 0):
            raise ValueError("Standard uncertainty must be finite and nonnegative")
        if (
            not isinstance(self.coverage_factor, int)
            or isinstance(self.coverage_factor, bool)
            or self.coverage_factor < 1
        ):
            raise ValueError("Coverage factor must be a positive integer")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("Quantity requires a documented provenance tag")
        if not isinstance(self.unit, str):
            raise TypeError("Unit is a reporting string, not a unit-conversion type")

    @classmethod
    def derived(
        cls,
        value: float,
        u: float | None,
        unit: str,
        *,
        inputs: Mapping[str, Quantity],
        formula: str,
        method: str | None = None,
        coverage_factor: int = 1,
        estimated: bool = False,
    ) -> Quantity:
        """Record named inputs and propagate origin; u is explicitly supplied.

        This constructor does not infer a numerical uncertainty equation or
        correlations. Future aero functions must compute and document those.
        """
        if not formula.strip() or any(not name.strip() for name in inputs):
            raise ValueError("Derived formula and input names must be nonempty")
        return cls(
            value,
            u,
            unit,
            derived_provenance((item.provenance for item in inputs.values()), estimated=estimated),
            coverage_factor,
            formula,
            method,
            tuple(inputs),
        )

    def __str__(self) -> str:
        return format_quantity(self)


def format_quantity(quantity: Quantity) -> str:
    """Round expanded uncertainty to two significant figures, then align value.

    Decimal strings prevent binary-float rounding from creating false precision
    at decimal carry boundaries. Unresolved status uses standard u, not k*u.
    """
    unit = f" {quantity.unit}" if quantity.unit else ""
    tag = f" [{quantity.provenance.value}]"
    value = Decimal(str(quantity.value))
    if quantity.u is None:
        return f"{value:f}{unit}{tag} — uncertainty not established"
    standard_u = Decimal(str(quantity.u))
    expanded_u = standard_u * quantity.coverage_factor
    if expanded_u == 0:
        numeric = f"{value:f} ± 0"
    else:
        place = expanded_u.adjusted() - 1
        with localcontext() as context:
            context.prec = max(34, value.adjusted() - place + 4)
            rounded_u = expanded_u.quantize(Decimal(1).scaleb(place), rounding=ROUND_HALF_UP)
            # A carry such as 0.0996 -> 0.100 needs a new decimal place: 0.10.
            place = rounded_u.adjusted() - 1
            step = Decimal(1).scaleb(place)
            rounded_u = expanded_u.quantize(step, rounding=ROUND_HALF_UP)
            rounded_value = value.quantize(step, rounding=ROUND_HALF_UP)
            if rounded_value == 0:
                rounded_value = abs(rounded_value)
            numeric = f"{rounded_value:f} ± {rounded_u:f}"
    coverage = f" (k={quantity.coverage_factor})" if quantity.coverage_factor != 1 else ""
    warning = " < 3σ — not resolved" if abs(value) < 3 * standard_u else ""
    return f"{numeric}{unit}{tag}{coverage}{warning}"
