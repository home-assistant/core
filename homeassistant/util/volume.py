"""Volume conversion util functions."""
from __future__ import annotations

from numbers import Number

from homeassistant.const import (
    UNIT_NOT_RECOGNIZED_TEMPLATE,
    VOLUME,
    VOLUME_CUBIC_FEET,
    VOLUME_CUBIC_METERS,
    VOLUME_FLUID_OUNCE,
    VOLUME_GALLONS,
    VOLUME_LITERS,
    VOLUME_MILLILITERS,
)

from .distance import FOOT_TO_M, IN_TO_M

VALID_UNITS: tuple[str, ...] = (
    VOLUME_LITERS,
    VOLUME_MILLILITERS,
    VOLUME_GALLONS,
    VOLUME_FLUID_OUNCE,
    VOLUME_CUBIC_METERS,
    VOLUME_CUBIC_FEET,
)

ML_TO_L = 0.001  # 1 mL = 0.001 L
CUBIC_METER_TO_L = 1000  # 1 m3 = 1000 L
GALLON_TO_L = 231 * pow(IN_TO_M, 3) * CUBIC_METER_TO_L  # US gallon is 231 cubic inches
FLUID_OUNCE_TO_L = GALLON_TO_L / 128  # 128 fluid ounces in a US gallon
CUBIC_FOOT_TO_L = CUBIC_METER_TO_L * pow(FOOT_TO_M, 3)

# Units in terms of L
UNIT_CONVERSION: dict[str, float] = {
    VOLUME_LITERS: 1,
    VOLUME_MILLILITERS: 1 / ML_TO_L,
    VOLUME_GALLONS: 1 / GALLON_TO_L,
    VOLUME_FLUID_OUNCE: 1 / FLUID_OUNCE_TO_L,
    VOLUME_CUBIC_METERS: 1 / CUBIC_METER_TO_L,
    VOLUME_CUBIC_FEET: 1 / CUBIC_FOOT_TO_L,
}


def liter_to_gallon(liter: float) -> float:
    """Convert a volume measurement in Liter to Gallon."""
    return _convert(liter, VOLUME_LITERS, VOLUME_GALLONS)


def gallon_to_liter(gallon: float) -> float:
    """Convert a volume measurement in Gallon to Liter."""
    return _convert(gallon, VOLUME_GALLONS, VOLUME_LITERS)


def cubic_meter_to_cubic_feet(cubic_meter: float) -> float:
    """Convert a volume measurement in cubic meter to cubic feet."""
    return _convert(cubic_meter, VOLUME_CUBIC_METERS, VOLUME_CUBIC_FEET)


def cubic_feet_to_cubic_meter(cubic_feet: float) -> float:
    """Convert a volume measurement in cubic feet to cubic meter."""
    return _convert(cubic_feet, VOLUME_CUBIC_FEET, VOLUME_CUBIC_METERS)


def convert(volume: float, from_unit: str, to_unit: str) -> float:
    """Convert a temperature from one unit to another."""
    if from_unit not in VALID_UNITS:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(from_unit, VOLUME))
    if to_unit not in VALID_UNITS:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(to_unit, VOLUME))

    if not isinstance(volume, Number):
        raise TypeError(f"{volume} is not of numeric type")

    if from_unit == to_unit:
        return volume
    return _convert(volume, from_unit, to_unit)


def _convert(volume: float, from_unit: str, to_unit: str) -> float:
    """Convert a temperature from one unit to another, bypassing checks."""
    liters = volume / UNIT_CONVERSION[from_unit]
    return liters * UNIT_CONVERSION[to_unit]
