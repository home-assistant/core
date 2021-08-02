"""Distance util functions."""
from __future__ import annotations

from numbers import Number

from homeassistant.const import (
    SPEED,
    SPEED_INCHES_PER_DAY,
    SPEED_INCHES_PER_HOUR,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    SPEED_MILLIMETERS_PER_DAY,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
)

VALID_UNITS: tuple[str, ...] = (
    SPEED_METERS_PER_SECOND,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_MILES_PER_HOUR,
    SPEED_MILLIMETERS_PER_DAY,
    SPEED_INCHES_PER_DAY,
    SPEED_INCHES_PER_HOUR,
)

# Units in terms of m/s
UNIT_CONVERSION: dict[str, float] = {
    SPEED_METERS_PER_SECOND: 1,
    SPEED_KILOMETERS_PER_HOUR: 3.6,
    SPEED_MILES_PER_HOUR: 2.2369363,
    SPEED_MILLIMETERS_PER_DAY: 86400000,
    SPEED_INCHES_PER_DAY: 3401574.8031496,
    SPEED_INCHES_PER_HOUR: 141732.2834646,
}


def convert(value: float, unit_1: str, unit_2: str) -> float:
    """Convert one unit of measurement to another."""
    if unit_1 not in VALID_UNITS:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit_1, SPEED))
    if unit_2 not in VALID_UNITS:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit_2, SPEED))

    if not isinstance(value, Number):
        raise TypeError(f"{value} is not of numeric type")

    if unit_1 == unit_2:
        return value

    mph = value / UNIT_CONVERSION[unit_1]
    return mph * UNIT_CONVERSION[unit_2]
