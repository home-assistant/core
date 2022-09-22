"""Pressure util functions."""
from __future__ import annotations

from numbers import Number

from homeassistant.const import (
    PRESSURE,
    PRESSURE_BAR,
    PRESSURE_CBAR,
    PRESSURE_HPA,
    PRESSURE_INHG,
    PRESSURE_KPA,
    PRESSURE_MBAR,
    PRESSURE_MMHG,
    PRESSURE_PA,
    PRESSURE_PSI,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
)

VALID_UNITS: tuple[str, ...] = (
    PRESSURE_PA,
    PRESSURE_HPA,
    PRESSURE_KPA,
    PRESSURE_BAR,
    PRESSURE_CBAR,
    PRESSURE_MBAR,
    PRESSURE_INHG,
    PRESSURE_PSI,
    PRESSURE_MMHG,
)

UNIT_CONVERSION: dict[str, float] = {
    PRESSURE_PA: 1,
    PRESSURE_HPA: 1 / 100,
    PRESSURE_KPA: 1 / 1000,
    PRESSURE_BAR: 1 / 100000,
    PRESSURE_CBAR: 1 / 1000,
    PRESSURE_MBAR: 1 / 100,
    PRESSURE_INHG: 1 / 3386.389,
    PRESSURE_PSI: 1 / 6894.757,
    PRESSURE_MMHG: 1 / 133.322,
}


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert one unit of measurement to another."""
    if from_unit not in VALID_UNITS:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(from_unit, PRESSURE))
    if to_unit not in VALID_UNITS:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(to_unit, PRESSURE))

    if not isinstance(value, Number):
        raise TypeError(f"{value} is not of numeric type")

    if from_unit == to_unit:
        return value

    pascals = value / UNIT_CONVERSION[from_unit]
    return pascals * UNIT_CONVERSION[to_unit]
