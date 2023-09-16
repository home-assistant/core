"""Distance util functions."""
from __future__ import annotations

# pylint: disable-next=hass-deprecated-import
from homeassistant.const import (  # noqa: F401
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
from homeassistant.helpers.frame import report

from .unit_conversion import (  # noqa: F401
    _FOOT_TO_M as FOOT_TO_M,
    _HRS_TO_SECS as HRS_TO_SECS,
    _IN_TO_M as IN_TO_M,
    _KM_TO_M as KM_TO_M,
    _MILE_TO_M as MILE_TO_M,
    _NAUTICAL_MILE_TO_M as NAUTICAL_MILE_TO_M,
    SpeedConverter,
)

# pylint: disable-next=protected-access
UNIT_CONVERSION: dict[str | None, float] = SpeedConverter._UNIT_CONVERSION
VALID_UNITS = SpeedConverter.VALID_UNITS


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert one unit of measurement to another."""
    report(
        (
            "uses speed utility. This is deprecated since 2022.10 and will "
            "stop working in Home Assistant 2023.4, it should be updated to use "
            "unit_conversion.SpeedConverter instead"
        ),
        error_if_core=False,
    )
    return SpeedConverter.convert(value, from_unit, to_unit)
