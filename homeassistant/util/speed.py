"""Distance util functions."""
from __future__ import annotations

from numbers import Number

from homeassistant.const import (
    SPEED,
    SPEED_FEET_PER_SECOND,
    SPEED_INCHES_PER_DAY,
    SPEED_INCHES_PER_HOUR,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_KNOTS,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    SPEED_MILLIMETERS_PER_DAY,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
)

VALID_UNITS: tuple[str, ...] = (
    SPEED_FEET_PER_SECOND,
    SPEED_INCHES_PER_DAY,
    SPEED_INCHES_PER_HOUR,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_KNOTS,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    SPEED_MILLIMETERS_PER_DAY,
)

FOOT_TO_M = 0.3048
HRS_TO_SECS = 60 * 60  # 1 hr = 3600 seconds
IN_TO_M = 0.0254
KM_TO_M = 1000  # 1 km = 1000 m
MILE_TO_M = 1609.344
NAUTICAL_MILE_TO_M = 1852  # 1 nautical mile = 1852 m

# Units in terms of m/s
UNIT_CONVERSION: dict[str, float] = {
    SPEED_FEET_PER_SECOND: 1 / FOOT_TO_M,
    SPEED_INCHES_PER_DAY: (24 * HRS_TO_SECS) / IN_TO_M,
    SPEED_INCHES_PER_HOUR: HRS_TO_SECS / IN_TO_M,
    SPEED_KILOMETERS_PER_HOUR: HRS_TO_SECS / KM_TO_M,
    SPEED_KNOTS: HRS_TO_SECS / NAUTICAL_MILE_TO_M,
    SPEED_METERS_PER_SECOND: 1,
    SPEED_MILES_PER_HOUR: HRS_TO_SECS / MILE_TO_M,
    SPEED_MILLIMETERS_PER_DAY: (24 * HRS_TO_SECS) * 1000,
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
