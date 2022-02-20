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

HRS_TO_SECS = 60 * 60  # 1 hr = 3600 seconds
KM_TO_M = 1000  # 1 km = 1000 m
KM_TO_MILE = 0.62137119  # 1 km = 0.62137119 mi
M_TO_IN = 39.3700787  # 1 m = 39.3700787 in

# Units in terms of m/s
UNIT_CONVERSION: dict[str, float] = {
    SPEED_METERS_PER_SECOND: 1,
    SPEED_KILOMETERS_PER_HOUR: HRS_TO_SECS / KM_TO_M,
    SPEED_MILES_PER_HOUR: HRS_TO_SECS * KM_TO_MILE / KM_TO_M,
    SPEED_MILLIMETERS_PER_DAY: (24 * HRS_TO_SECS) * 1000,
    SPEED_INCHES_PER_DAY: (24 * HRS_TO_SECS) * M_TO_IN,
    SPEED_INCHES_PER_HOUR: HRS_TO_SECS * M_TO_IN,
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

    meters_per_second = value / UNIT_CONVERSION[unit_1]
    return meters_per_second * UNIT_CONVERSION[unit_2]
