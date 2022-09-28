"""Temperature util functions."""
from homeassistant.const import (  # pylint: disable=unused-import # noqa: F401
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TEMP_KELVIN,
    TEMPERATURE,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
)

from .unit_conversion import TemperatureConverter

VALID_UNITS = TemperatureConverter.VALID_UNITS


def fahrenheit_to_celsius(fahrenheit: float, interval: bool = False) -> float:
    """Convert a temperature in Fahrenheit to Celsius."""
    # Need to add warning when core migration finished
    return TemperatureConverter.fahrenheit_to_celsius(fahrenheit, interval)


def kelvin_to_celsius(kelvin: float, interval: bool = False) -> float:
    """Convert a temperature in Kelvin to Celsius."""
    # Need to add warning when core migration finished
    return TemperatureConverter.kelvin_to_celsius(kelvin, interval)


def celsius_to_fahrenheit(celsius: float, interval: bool = False) -> float:
    """Convert a temperature in Celsius to Fahrenheit."""
    # Need to add warning when core migration finished
    return TemperatureConverter.celsius_to_fahrenheit(celsius, interval)


def celsius_to_kelvin(celsius: float, interval: bool = False) -> float:
    """Convert a temperature in Celsius to Fahrenheit."""
    # Need to add warning when core migration finished
    return TemperatureConverter.celsius_to_kelvin(celsius, interval)


def convert(
    temperature: float, from_unit: str, to_unit: str, interval: bool = False
) -> float:
    """Convert a temperature from one unit to another."""
    # Need to add warning when core migration finished
    return TemperatureConverter.convert(
        temperature, from_unit, to_unit, interval=interval
    )
