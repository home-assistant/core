"""Typing Helpers for Home Assistant."""
from __future__ import annotations

from typing import Protocol


class UnitConverter(Protocol):
    """Define the format of a conversion utility."""

    VALID_UNITS: tuple[str, ...]
    NORMALIZED_UNIT: str

    def convert(self, value: float, from_unit: str, to_unit: str) -> float:
        """Convert one unit of measurement to another."""

    def to_normalized_unit(self, value: float, from_unit: str) -> float:
        """Convert one unit of measurement to the normalized unit.

        Warning: sanity checks for `value` and `from_unit` are bypassed
        and should be validate prior to calling this function.
        """
