"""Distance util functions."""
from __future__ import annotations

from homeassistant.const import (  # pylint: disable=unused-import # noqa: F401
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

from .unit_conversion import (  # pylint: disable=unused-import # noqa: F401
    FOOT_TO_M,
    HRS_TO_SECS,
    IN_TO_M,
    KM_TO_M,
    MILE_TO_M,
    NAUTICAL_MILE_TO_M,
    SpeedConverter,
)

UNIT_CONVERSION = SpeedConverter.UNIT_CONVERSION
VALID_UNITS = SpeedConverter.VALID_UNITS


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert one unit of measurement to another."""
    return SpeedConverter.convert(value, from_unit, to_unit)
