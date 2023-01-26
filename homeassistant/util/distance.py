"""Distance util functions."""
from __future__ import annotations

from collections.abc import Callable

# pylint: disable-next=unused-import,hass-deprecated-import
from homeassistant.const import (  # noqa: F401
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

TO_METERS: dict[str, Callable[[float], float]] = {
    LENGTH_METERS: lambda meters: meters,
    LENGTH_MILES: lambda miles: miles * 1609.344,
    LENGTH_YARD: lambda yards: yards * 0.9144,
    LENGTH_FEET: lambda feet: feet * 0.3048,
    LENGTH_INCHES: lambda inches: inches * 0.0254,
    LENGTH_KILOMETERS: lambda kilometers: kilometers * 1000,
    LENGTH_CENTIMETERS: lambda centimeters: centimeters * 0.01,
    LENGTH_MILLIMETERS: lambda millimeters: millimeters * 0.001,
}

METERS_TO: dict[str, Callable[[float], float]] = {
    LENGTH_METERS: lambda meters: meters,
    LENGTH_MILES: lambda meters: meters * 0.000621371,
    LENGTH_YARD: lambda meters: meters * 1.09361,
    LENGTH_FEET: lambda meters: meters * 3.28084,
    LENGTH_INCHES: lambda meters: meters * 39.3701,
    LENGTH_KILOMETERS: lambda meters: meters * 0.001,
    LENGTH_CENTIMETERS: lambda meters: meters * 100,
    LENGTH_MILLIMETERS: lambda meters: meters * 1000,
}


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert one unit of measurement to another."""
    report(
        (
            "uses distance utility. This is deprecated since 2022.10 and will "
            "stop working in Home Assistant 2023.4, it should be updated to use "
            "unit_conversion.DistanceConverter instead"
        ),
        error_if_core=False,
    )
    return DistanceConverter.convert(value, from_unit, to_unit)
