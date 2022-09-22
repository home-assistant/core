"""Volume conversion util functions."""
from __future__ import annotations

from homeassistant.const import (  # pylint: disable=unused-import # noqa: F401
    UNIT_NOT_RECOGNIZED_TEMPLATE,
    VOLUME,
    VOLUME_CUBIC_FEET,
    VOLUME_CUBIC_METERS,
    VOLUME_FLUID_OUNCE,
    VOLUME_GALLONS,
    VOLUME_LITERS,
    VOLUME_MILLILITERS,
)

from .unit_conversion import VolumeConverter

UNIT_CONVERSION = VolumeConverter.UNIT_CONVERSION
VALID_UNITS = VolumeConverter.VALID_UNITS


def liter_to_gallon(liter: float) -> float:
    """Convert a volume measurement in Liter to Gallon."""
    # Need to add warning when core migration finished
    return _convert(liter, VOLUME_LITERS, VOLUME_GALLONS)


def gallon_to_liter(gallon: float) -> float:
    """Convert a volume measurement in Gallon to Liter."""
    # Need to add warning when core migration finished
    return _convert(gallon, VOLUME_GALLONS, VOLUME_LITERS)


def cubic_meter_to_cubic_feet(cubic_meter: float) -> float:
    """Convert a volume measurement in cubic meter to cubic feet."""
    # Need to add warning when core migration finished
    return _convert(cubic_meter, VOLUME_CUBIC_METERS, VOLUME_CUBIC_FEET)


def cubic_feet_to_cubic_meter(cubic_feet: float) -> float:
    """Convert a volume measurement in cubic feet to cubic meter."""
    # Need to add warning when core migration finished
    return _convert(cubic_feet, VOLUME_CUBIC_FEET, VOLUME_CUBIC_METERS)


def convert(volume: float, from_unit: str, to_unit: str) -> float:
    """Convert a volume from one unit to another."""
    # Need to add warning when core migration finished
    return VolumeConverter.convert(volume, from_unit, to_unit)


def _convert(volume: float, from_unit: str, to_unit: str) -> float:
    """Convert a volume from one unit to another, bypassing checks."""
    cubic_meter = volume / UNIT_CONVERSION[from_unit]
    return cubic_meter * UNIT_CONVERSION[to_unit]
