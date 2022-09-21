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

from .distance import (
    FOOT_TO_M,
    IN_TO_M,
    KM_TO_M,
    MILE_TO_M,
    MM_TO_M,
    NAUTICAL_MILE_TO_M,
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

HRS_TO_SECS = 60 * 60  # 1 hr = 3600 seconds
DAYS_TO_SECS = 24 * HRS_TO_SECS  # 1 day = 24 hours = 86400 seconds

# Units in terms of m/s
UNIT_CONVERSION: dict[str, float] = {
    SPEED_FEET_PER_SECOND: 1 / FOOT_TO_M,
    SPEED_INCHES_PER_DAY: DAYS_TO_SECS / IN_TO_M,
    SPEED_INCHES_PER_HOUR: HRS_TO_SECS / IN_TO_M,
    SPEED_KILOMETERS_PER_HOUR: HRS_TO_SECS / KM_TO_M,
    SPEED_KNOTS: HRS_TO_SECS / NAUTICAL_MILE_TO_M,
    SPEED_METERS_PER_SECOND: 1,
    SPEED_MILES_PER_HOUR: HRS_TO_SECS / MILE_TO_M,
    SPEED_MILLIMETERS_PER_DAY: DAYS_TO_SECS / MM_TO_M,
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
