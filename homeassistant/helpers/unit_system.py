"""Unit system helper class and methods."""

import logging
from homeassistant.const import (
    TEMP_CELSIUS, TEMP_FAHRENHEIT, LENGTH_CENTIMETERS, LENGTH_METERS,
    LENGTH_KILOMETERS, LENGTH_INCHES, LENGTH_FEET, LENGTH_YARD, LENGTH_MILES,
    VOLUME_LITERS, VOLUME_MILLILITERS, VOLUME_GALLONS, VOLUME_FLUID_OUNCE,
    MASS_GRAMS, MASS_KILOGRAMS, MASS_OUNCES, MASS_POUNDS, SYSTEM_METRIC,
    SYSTEM_IMPERIAL)

_LOGGER = logging.getLogger(__name__)

TYPE_LENGTH = 'length'  # type: str
TYPE_MASS = 'mass'  # type: str
TYPE_VOLUME = 'volume'  # type: str
TYPE_TEMPERATURE = 'temperature'  # type: str

LENGTH_UNITS = [
    LENGTH_MILES,
    LENGTH_YARD,
    LENGTH_FEET,
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_CENTIMETERS,
]

MASS_UNITS = [
    MASS_POUNDS,
    MASS_OUNCES,
    MASS_KILOGRAMS,
    MASS_GRAMS,
]

VOLUME_UNITS = [
    VOLUME_GALLONS,
    VOLUME_FLUID_OUNCE,
    VOLUME_LITERS,
    VOLUME_MILLILITERS,
]

TEMPERATURE_UNITS = [
    TEMP_FAHRENHEIT,
    TEMP_CELSIUS,
]

NOT_RECOGNIZED_TEMPLATE = '{} is not a recognized {} unit.'  # type: str


def is_valid_unit(unit: str, unit_type: str) -> bool:
    """Check if the unit is valid for it's type."""
    if unit_type == TYPE_LENGTH:
        units = LENGTH_UNITS
    elif unit_type == TYPE_TEMPERATURE:
        units = TEMPERATURE_UNITS
    elif unit_type == TYPE_MASS:
        units = MASS_UNITS
    elif unit_type == TYPE_VOLUME:
        units = VOLUME_UNITS
    else:
        return False

    return unit in units


class UnitSystem(object):
    def __init__(self, name, temperature, length, volume, mass):
        """Initialize the unit system object."""
        if not is_valid_unit(unit, unit_type) for unit, unit_type in [
            (temperature, TYPE_TEMPERATURE),
            (length, TYPE_LENGTH),
            (volume, TYPE_VOLUME),
            (mass, TYPE_MASS)]:
            raise ValueError(
                NOT_RECOGNIZED_TEMPLATE.format(unit, unit_type))

        self.name = name
        self.temperature = temperature
        self.length = length
        self.volume = volume
        self.mass = mass