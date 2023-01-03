"""Volume conversion util functions."""
from __future__ import annotations

# pylint: disable-next=unused-import,hass-deprecated-import
from homeassistant.const import (  # noqa: F401
    UNIT_NOT_RECOGNIZED_TEMPLATE,
    VOLUME,
    VOLUME_CUBIC_FEET,
    VOLUME_CUBIC_METERS,
    VOLUME_FLUID_OUNCE,
    VOLUME_GALLONS,
    VOLUME_LITERS,
    VOLUME_MILLILITERS,
)
from homeassistant.helpers.frame import report

from .unit_conversion import VolumeConverter

VALID_UNITS = VolumeConverter.VALID_UNITS


def liter_to_gallon(liter: float) -> float:
    """Convert a volume measurement in Liter to Gallon."""
    return convert(liter, VOLUME_LITERS, VOLUME_GALLONS)


def gallon_to_liter(gallon: float) -> float:
    """Convert a volume measurement in Gallon to Liter."""
    return convert(gallon, VOLUME_GALLONS, VOLUME_LITERS)


def cubic_meter_to_cubic_feet(cubic_meter: float) -> float:
    """Convert a volume measurement in cubic meter to cubic feet."""
    return convert(cubic_meter, VOLUME_CUBIC_METERS, VOLUME_CUBIC_FEET)


def cubic_feet_to_cubic_meter(cubic_feet: float) -> float:
    """Convert a volume measurement in cubic feet to cubic meter."""
    return convert(cubic_feet, VOLUME_CUBIC_FEET, VOLUME_CUBIC_METERS)


def convert(volume: float, from_unit: str, to_unit: str) -> float:
    """Convert a volume from one unit to another."""
    report(
        (
            "uses volume utility. This is deprecated since 2022.10 and will "
            "stop working in Home Assistant 2023.4, it should be updated to use "
            "unit_conversion.VolumeConverter instead"
        ),
        error_if_core=False,
    )
    return VolumeConverter.convert(volume, from_unit, to_unit)
