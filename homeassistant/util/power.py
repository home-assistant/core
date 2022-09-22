"""Power util functions."""
from __future__ import annotations

from numbers import Number

from homeassistant.const import (
    POWER_KILO_WATT,
    POWER_WATT,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
)

VALID_UNITS: tuple[str, ...] = (
    POWER_WATT,
    POWER_KILO_WATT,
)

UNIT_CONVERSION: dict[str, float] = {
    POWER_WATT: 1,
    POWER_KILO_WATT: 1 / 1000,
}

NORMALIZED_UNIT = POWER_WATT


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert one unit of measurement to another."""
    if from_unit not in VALID_UNITS:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(from_unit, "power"))
    if to_unit not in VALID_UNITS:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(to_unit, "power"))

    if not isinstance(value, Number):
        raise TypeError(f"{value} is not of numeric type")

    if from_unit == to_unit:
        return value

    return _convert(value, from_unit, to_unit)


def to_normalized_unit(value: float, from_unit: str) -> float:
    """Convert a power from one unit to W."""
    if from_unit == NORMALIZED_UNIT:
        return value
    return _convert(value, from_unit, NORMALIZED_UNIT)


def _convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert a power from one unit to another, bypassing checks."""
    watts = value / UNIT_CONVERSION[from_unit]
    return watts * UNIT_CONVERSION[to_unit]
