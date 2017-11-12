"""Temperature util functions."""
from math import log as ln

from homeassistant.const import (
    TEMP_CELSIUS, TEMP_FAHRENHEIT, UNIT_NOT_RECOGNIZED_TEMPLATE, TEMPERATURE)


def fahrenheit_to_celsius(fahrenheit: float) -> float:
    """Convert a temperature in Fahrenheit to Celsius."""
    return (fahrenheit - 32.0) / 1.8


def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert a temperature in Celsius to Fahrenheit."""
    return celsius * 1.8 + 32.0


def convert(temperature: float, from_unit: str, to_unit: str) -> float:
    """Convert a temperature from one unit to another."""
    if from_unit not in (TEMP_CELSIUS, TEMP_FAHRENHEIT):
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(
            from_unit, TEMPERATURE))
    if to_unit not in (TEMP_CELSIUS, TEMP_FAHRENHEIT):
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(
            to_unit, TEMPERATURE))

    if from_unit == to_unit:
        return temperature
    elif from_unit == TEMP_CELSIUS:
        return celsius_to_fahrenheit(temperature)
    return fahrenheit_to_celsius(temperature)


def calculate_dewpoint(temperature: float, humidity: float,
                       units: str) -> float:
    """Calculate dewpoint from temperature and relative humidity.

    Uses the Magnus formula approximation.
    See https://en.wikipedia.org/wiki/Dew_point#Calculating_the_dew_point

    Humidity should be a percentage (0-100)
    """
    if units not in (TEMP_CELSIUS, TEMP_FAHRENHEIT):
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(
            units, TEMPERATURE))
    if humidity <= 0 or humidity > 100:
        # Zero relative humidity doesn't work because natural log of zero
        # is undefined
        raise ValueError('Relative humidity value {} invalid, '
                         'must be 0 < rh <= 100'.format(humidity))
    temp = convert(temperature, units, TEMP_CELSIUS)
    const_b = 17.67
    const_c = 243.5
    gamma = ln(humidity / 100) + (const_b * temp / (const_c + temp))
    dewpoint = (const_c * gamma) / (const_b - gamma)
    return convert(dewpoint, TEMP_CELSIUS, units)
