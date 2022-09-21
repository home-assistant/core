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


def convert(value: float, unit_1: str, unit_2: str) -> float:
    """Convert one unit of measurement to another."""
    if unit_1 not in VALID_UNITS:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit_1, "power"))
    if unit_2 not in VALID_UNITS:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit_2, "power"))

    if not isinstance(value, Number):
        raise TypeError(f"{value} is not of numeric type")

    if unit_1 == unit_2:
        return value

    watts = value / UNIT_CONVERSION[unit_1]
    return watts * UNIT_CONVERSION[unit_2]
