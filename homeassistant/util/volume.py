"""Volume conversion util functions."""

import logging
from numbers import Number
from homeassistant.const import (VOLUME_LITERS, VOLUME_MILLILITERS,
                                 VOLUME_GALLONS, VOLUME_FLUID_OUNCE,
                                 VOLUME, UNIT_NOT_RECOGNIZED_TEMPLATE)

_LOGGER = logging.getLogger(__name__)

VALID_UNITS = [VOLUME_LITERS, VOLUME_MILLILITERS, VOLUME_GALLONS,
               VOLUME_FLUID_OUNCE]


def __liter_to_gallon(liter: float) -> float:
    """Convert a volume measurement in Liter to Gallon."""
    return liter * .2642


def __gallon_to_liter(gallon: float) -> float:
    """Convert a volume measurement in Gallon to Liter."""
    return gallon * 3.785


def convert(volume: float, from_unit: str, to_unit: str) -> float:
    """Convert a temperature from one unit to another."""
    if from_unit not in VALID_UNITS:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(from_unit,
                                                             VOLUME))
    if to_unit not in VALID_UNITS:
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(to_unit, VOLUME))

    if not isinstance(volume, Number):
        raise TypeError('{} is not of numeric type'.format(volume))

    if from_unit == to_unit:
        return volume

    result = volume
    if from_unit == VOLUME_LITERS and to_unit == VOLUME_GALLONS:
        result = __liter_to_gallon(volume)
    elif from_unit == VOLUME_GALLONS and to_unit == VOLUME_LITERS:
        result = __gallon_to_liter(volume)

    return result
