"""Energy util functions."""
from __future__ import annotations

from numbers import Number

from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    ENERGY_MEGA_WATT_HOUR,
    ENERGY_WATT_HOUR,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
)

VALID_UNITS: tuple[str, ...] = (
    ENERGY_WATT_HOUR,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_MEGA_WATT_HOUR,
)

UNIT_CONVERSION: dict[str, float] = {
    ENERGY_WATT_HOUR: 1 * 1000,
    ENERGY_KILO_WATT_HOUR: 1,
    ENERGY_MEGA_WATT_HOUR: 1 / 1000,
}

NORMALIZED_UNIT = ENERGY_KILO_WATT_HOUR


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert one unit of measurement to another."""
    if from_unit not in VALID_UNITS:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(from_unit, "energy"))
    if to_unit not in VALID_UNITS:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(to_unit, "energy"))

    if not isinstance(value, Number):
        raise TypeError(f"{value} is not of numeric type")

    if from_unit == to_unit:
        return value

    return _convert(value, from_unit, to_unit)


def to_normalized_unit(value: float, from_unit: str) -> float:
    """Convert an energy from one unit to kWh."""
    if from_unit == NORMALIZED_UNIT:
        return value
    return _convert(value, from_unit, NORMALIZED_UNIT)


def _convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert an energy from one unit to another, bypassing checks."""
    watthours = value / UNIT_CONVERSION[from_unit]
    return watthours * UNIT_CONVERSION[to_unit]
