"""The five origin labels defined by measurement-model.md section 1."""

from collections.abc import Iterable
from enum import StrEnum


class Provenance(StrEnum):
    MEASURED = "MEASURED"
    DERIVED = "DERIVED"
    ESTIMATED = "ESTIMATED"
    ASSUMED = "ASSUMED"
    USER_PROVIDED = "USER_PROVIDED"


def derived_provenance(inputs: Iterable[Provenance], *, estimated: bool = False) -> Provenance:
    """Demote computed results when a source is assumed or already estimated.

    USER_PROVIDED records an origin, not an automatic assumption. An empirical
    model must explicitly pass estimated=True even if every input was measured.
    """
    sources = tuple(inputs)
    if not sources:
        raise ValueError("A derived quantity must identify at least one input")
    if not all(isinstance(source, Provenance) for source in sources):
        raise TypeError("Input provenance must use the documented enum")
    if estimated or any(source in {Provenance.ASSUMED, Provenance.ESTIMATED} for source in sources):
        return Provenance.ESTIMATED
    return Provenance.DERIVED
