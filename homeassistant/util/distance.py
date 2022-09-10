"""Distance util functions."""
from __future__ import annotations

from numbers import Number

from homeassistant.const import (
    LENGTH,
    LENGTH_CENTIMETERS,
    LENGTH_FEET,
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    LENGTH_MILLIMETERS,
    LENGTH_YARD,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
)

VALID_UNITS: tuple[str, ...] = (
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    LENGTH_FEET,
    LENGTH_METERS,
    LENGTH_CENTIMETERS,
    LENGTH_MILLIMETERS,
    LENGTH_INCHES,
    LENGTH_YARD,
)

MM_TO_M = 0.001  # 1 mm = 0.001 m
CM_TO_M = 0.01  # 1 cm = 0.01 m
KM_TO_M = 1000  # 1 km = 1000 m

IN_TO_M = 0.0254  # 1 inch = 0.0254 m
FOOT_TO_M = IN_TO_M * 12  # 12 inches = 1 foot (0.3048 m)
YARD_TO_M = FOOT_TO_M * 3  # 3 feet = 1 yard (0.9144 m)
MILE_TO_M = YARD_TO_M * 1760  # 1760 yard = 1 mile (1609.344 m)

NAUTICAL_MILE_TO_M = 1852  # 1 nautical mile = 1852 m

UNIT_CONVERSION: dict[str, float] = {
    LENGTH_METERS: 1,
    LENGTH_MILLIMETERS: 1 / MM_TO_M,
    LENGTH_CENTIMETERS: 1 / CM_TO_M,
    LENGTH_KILOMETERS: 1 / KM_TO_M,
    LENGTH_INCHES: 1 / IN_TO_M,
    LENGTH_FEET: 1 / FOOT_TO_M,
    LENGTH_YARD: 1 / YARD_TO_M,
    LENGTH_MILES: 1 / MILE_TO_M,
}


def convert(value: float, unit_1: str, unit_2: str) -> float:
    """Convert one unit of measurement to another."""
    if unit_1 not in VALID_UNITS:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit_1, LENGTH))
    if unit_2 not in VALID_UNITS:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit_2, LENGTH))

    if not isinstance(value, Number):
        raise TypeError(f"{value} is not of numeric type")

    if unit_1 == unit_2 or unit_1 not in VALID_UNITS:
        return value

    meters: float = value / UNIT_CONVERSION[unit_1]

    return meters * UNIT_CONVERSION[unit_2]
