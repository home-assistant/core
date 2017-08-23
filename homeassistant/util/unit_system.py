"""Unit system helper class and methods."""

import logging
from numbers import Number

from homeassistant.const import (
    TEMP_CELSIUS, TEMP_FAHRENHEIT, LENGTH_CENTIMETERS, LENGTH_METERS,
    LENGTH_KILOMETERS, LENGTH_INCHES, LENGTH_FEET, LENGTH_YARD, LENGTH_MILES,
    VOLUME_LITERS, VOLUME_MILLILITERS, VOLUME_GALLONS, VOLUME_FLUID_OUNCE,
    MASS_GRAMS, MASS_KILOGRAMS, MASS_OUNCES, MASS_POUNDS,
    CONF_UNIT_SYSTEM_METRIC, CONF_UNIT_SYSTEM_IMPERIAL, LENGTH, MASS, VOLUME,
    TEMPERATURE, UNIT_NOT_RECOGNIZED_TEMPLATE)
from homeassistant.util import temperature as temperature_util
from homeassistant.util import distance as distance_util

_LOGGER = logging.getLogger(__name__)

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
    else:
        return False

    return unit in units


class UnitSystem(object):
    """A container for units of measure."""

    def __init__(self: object, name: str, temperature: str, length: str,
                 volume: str, mass: str) -> None:
        """Initialize the unit system object."""
        errors = \
            ', '.join(UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit, unit_type)
                      for unit, unit_type in [
                          (temperature, TEMPERATURE),
                          (length, LENGTH),
                          (volume, VOLUME),
                          (mass, MASS), ]
                      if not is_valid_unit(unit, unit_type))  # type: str

        if errors:
            raise ValueError(errors)

        self.name = name
        self.temperature_unit = temperature
        self.length_unit = length
        self.mass_unit = mass
        self.volume_unit = volume

    @property
    def is_metric(self: object) -> bool:
        """Determine if this is the metric unit system."""
        return self.name == CONF_UNIT_SYSTEM_METRIC

    def temperature(self: object, temperature: float, from_unit: str) -> float:
        """Convert the given temperature to this unit system."""
        if not isinstance(temperature, Number):
            raise TypeError(
                '{} is not a numeric value.'.format(str(temperature)))

        return temperature_util.convert(temperature,
                                        from_unit, self.temperature_unit)

    def length(self: object, length: float, from_unit: str) -> float:
        """Convert the given length to this unit system return a float."""
        converted = self.length_with_display_obj(length, from_unit)
        return converted["value"]

    def length_with_display_obj(self: object, length: float,
                                from_unit: str) -> dict:
        """Convert the given length to this unit system return a dict."""
        if not isinstance(length, Number):
            raise TypeError('{} is not a numeric value.'.format(str(length)))

        to_unit = self.length_unit
        if self == METRIC_SYSTEM:
            if from_unit in (LENGTH_FEET, LENGTH_INCHES):
                to_unit = LENGTH_CENTIMETERS
            elif from_unit == LENGTH_YARD:
                to_unit = LENGTH_METERS
        elif self == IMPERIAL_SYSTEM:
            if from_unit == LENGTH_CENTIMETERS:
                to_unit = LENGTH_INCHES
            elif from_unit == LENGTH_METERS:
                to_unit = LENGTH_INCHES

        conv = distance_util.convert(
            length, from_unit, to_unit)  # type: float

        conversion_result = {}
        conversion_result["value"] = conv
        conversion_result["unit"] = to_unit
        return conversion_result

    def as_dict(self) -> dict:
        """Convert the unit system to a dictionary."""
        return {
            LENGTH: self.length_unit,
            MASS: self.mass_unit,
            TEMPERATURE: self.temperature_unit,
            VOLUME: self.volume_unit
        }

    def convert(self, state, unit_of_measure):
        """Generic conversion method."""
        converted = None
        try:
            if (unit_of_measure in (TEMP_CELSIUS, TEMP_FAHRENHEIT) and
                    unit_of_measure != self.temperature_unit):
                # Convert temperature if we detect one
                prec = len(state) - state.index('.') - 1 if '.' in state else 0
                temp = self.temperature(float(state), unit_of_measure)
                state = str(round(temp) if prec == 0 else round(temp, prec))
                converted = {}
                converted["value"] = state
                converted["units"] = self.temperature_unit
        except ValueError:
            # Could not convert state to float
            pass

        try:
            if (unit_of_measure in LENGTH_UNITS and
                    unit_of_measure != self.length_unit):
                # Convert length if we detect one
                prec = len(state) - state.index('.') - 1 if '.' in state else 0
                converted = self.length_with_display_obj(
                    float(state), unit_of_measure)
                length = converted["value"]
                state = str(round(length))
                if prec != 0:
                    state = round(length, prec)
                converted["value"] = state
        except ValueError:
            # Could not convert state to float
            pass

        return converted

METRIC_SYSTEM = UnitSystem(CONF_UNIT_SYSTEM_METRIC, TEMP_CELSIUS,
                           LENGTH_KILOMETERS, VOLUME_LITERS, MASS_GRAMS)

IMPERIAL_SYSTEM = UnitSystem(CONF_UNIT_SYSTEM_IMPERIAL, TEMP_FAHRENHEIT,
                             LENGTH_MILES, VOLUME_GALLONS, MASS_POUNDS)
