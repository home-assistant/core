"""Unit system helper class and methods."""

import logging
from numbers import Number
from typing import Tuple

from homeassistant.const import (
    TEMP_CELSIUS, TEMP_FAHRENHEIT,
    LENGTH_UNITS_IMPERIAL, LENGTH_UNITS_METRIC,
    LENGTH_MILLIMETERS, LENGTH_CENTIMETERS, LENGTH_METERS, LENGTH_KILOMETERS,
    LENGTH_INCHES, LENGTH_FEET, LENGTH_YARD, LENGTH_MILES,
    VOLUME_LITERS, VOLUME_MILLILITERS, VOLUME_GALLONS, VOLUME_FLUID_OUNCE,
    MASS_GRAMS, MASS_KILOGRAMS, MASS_OUNCES, MASS_POUNDS,
    SPEED_UNITS_IMPERIAL, SPEED_UNITS_METRIC,
    SPEED_MS, SPEED_KMH, SPEED_FTS, SPEED_MPH,
    CONF_UNIT_SYSTEM_METRIC, CONF_UNIT_SYSTEM_IMPERIAL,
    LENGTH, MASS, VOLUME, SPEED, TEMPERATURE,
    UNIT_NOT_RECOGNIZED_TEMPLATE)
from homeassistant.util import temperature as temperature_util
from homeassistant.util import distance as distance_util
from homeassistant.util import speed as speed_util

_LOGGER = logging.getLogger(__name__)

LENGTH_UNITS = [
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    LENGTH_FEET,
    LENGTH_YARD,
    LENGTH_INCHES,
    LENGTH_METERS,
    LENGTH_CENTIMETERS,
    LENGTH_MILLIMETERS,
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

SPEED_UNITS = [
    SPEED_MS,
    SPEED_KMH,
    SPEED_FTS,
    SPEED_MPH
]


def is_valid_unit(unit: str, unit_type: str) -> bool:
    """Check if the unit is valid for it's type."""
    if unit_type == LENGTH:
        units = LENGTH_UNITS
    elif unit_type == TEMPERATURE:
        units = TEMPERATURE_UNITS
    elif unit_type == MASS:
        units = MASS_UNITS
    elif unit_type == VOLUME:
        units = VOLUME_UNITS
    elif unit_type == SPEED:
        units = SPEED_UNITS
    else:
        return False

    return unit in units


class UnitSystem(object):
    """A container for units of measure."""

    def __init__(self: object, name: str, temperature: str, length: str,
                 volume: str, mass: str, speed: str) -> None:
        """Initialize the unit system object."""
        errors = \
            ', '.join(UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit, unit_type)
                      for unit, unit_type in [
                          (temperature, TEMPERATURE),
                          (length, LENGTH),
                          (volume, VOLUME),
                          (mass, MASS),
                          (speed, SPEED), ]
                      if not is_valid_unit(unit, unit_type))  # type: str

        if errors:
            raise ValueError(errors)

        self.name = name
        self.temperature_unit = temperature
        self.length_unit = length
        self.mass_unit = mass
        self.volume_unit = volume
        self.speed_unit = speed

    @property
    def is_metric(self: object) -> bool:
        """Determine if this is the metric unit system."""
        return self.name == CONF_UNIT_SYSTEM_METRIC

    def temperature(self: object, temperature: float, from_unit: str) -> float:
        """Convert the given temperature to this unit system."""
        if not isinstance(temperature, Number):
            raise TypeError(
                '{} is not a numeric value.'.format(str(temperature)))

        return temperature_util.convert(temperature, from_unit,
                                        self.temperature_unit)  # type: float

    def length(self: object, length: float,
               from_unit: str) -> Tuple[float, str]:
        """Convert the given length to this unit system."""
        if not isinstance(length, Number):
            raise TypeError('{} is not a numeric value.'.format(str(length)))
        if (from_unit in LENGTH_UNITS_METRIC and
                self.name is CONF_UNIT_SYSTEM_IMPERIAL):
            to_unit = LENGTH_UNITS_IMPERIAL[
                LENGTH_UNITS_METRIC.index(from_unit)]
        elif (from_unit in LENGTH_UNITS_IMPERIAL and
              self.name is CONF_UNIT_SYSTEM_METRIC):
            to_unit = LENGTH_UNITS_METRIC[
                LENGTH_UNITS_IMPERIAL.index(from_unit)]
        else:
            to_unit = from_unit

        return (distance_util.convert(length, from_unit, to_unit),
                to_unit)  # type: Tuple[float, str]

    def speed(self: object, speed: float, from_unit: str) -> float:
        """Convert the given speed to this unit system."""
        if not isinstance(speed, Number):
            raise TypeError('{} is not a numeric value.'.format(str(speed)))
        if (from_unit in SPEED_UNITS_METRIC and
                self.name is CONF_UNIT_SYSTEM_IMPERIAL):
            to_unit = SPEED_UNITS_IMPERIAL[
                SPEED_UNITS_METRIC.index(from_unit)]
        elif (from_unit in SPEED_UNITS_IMPERIAL and
              self.name is CONF_UNIT_SYSTEM_METRIC):
            to_unit = SPEED_UNITS_METRIC[
                SPEED_UNITS_IMPERIAL.index(from_unit)]
        else:
            to_unit = from_unit

        return (speed_util.convert(speed, from_unit, to_unit),
                to_unit)  # type: Tuple[float, str]

    def as_dict(self) -> dict:
        """Convert the unit system to a dictionary."""
        return {
            LENGTH: self.length_unit,
            MASS: self.mass_unit,
            TEMPERATURE: self.temperature_unit,
            VOLUME: self.volume_unit,
            SPEED: self.speed_unit
        }


METRIC_SYSTEM = UnitSystem(CONF_UNIT_SYSTEM_METRIC, TEMP_CELSIUS,
                           LENGTH_KILOMETERS, VOLUME_LITERS, MASS_GRAMS,
                           SPEED_KMH)

IMPERIAL_SYSTEM = UnitSystem(CONF_UNIT_SYSTEM_IMPERIAL, TEMP_FAHRENHEIT,
                             LENGTH_MILES, VOLUME_GALLONS, MASS_POUNDS,
                             SPEED_MPH)
