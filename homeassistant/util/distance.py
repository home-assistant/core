"""Distance util functions."""
from __future__ import annotations

from homeassistant.const import (  # pylint: disable=unused-import # noqa: F401
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
from homeassistant.helpers.frame import report

from .unit_conversion import DistanceConverter

VALID_UNITS = DistanceConverter.VALID_UNITS


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert one unit of measurement to another."""
    report(
        "uses distance utility. This is deprecated since 2022.10 and will "
        "stop working in Home Assistant 2022.4, it should be updated to use "
        "unit_conversion.DistanceConverter instead",
        error_if_core=False,
    )
    return DistanceConverter.convert(value, from_unit, to_unit)
