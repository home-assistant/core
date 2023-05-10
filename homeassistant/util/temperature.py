"""Temperature util functions."""
# pylint: disable-next=unused-import,hass-deprecated-import
from homeassistant.const import (  # noqa: F401
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TEMP_KELVIN,
    TEMPERATURE,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
)
from homeassistant.helpers.frame import report

from .unit_conversion import TemperatureConverter

VALID_UNITS = TemperatureConverter.VALID_UNITS


def fahrenheit_to_celsius(fahrenheit: float, interval: bool = False) -> float:
    """Convert a temperature in Fahrenheit to Celsius."""
    return convert(fahrenheit, TEMP_FAHRENHEIT, TEMP_CELSIUS, interval)


def kelvin_to_celsius(kelvin: float, interval: bool = False) -> float:
    """Convert a temperature in Kelvin to Celsius."""
    return convert(kelvin, TEMP_KELVIN, TEMP_CELSIUS, interval)


def celsius_to_fahrenheit(celsius: float, interval: bool = False) -> float:
    """Convert a temperature in Celsius to Fahrenheit."""
    return convert(celsius, TEMP_CELSIUS, TEMP_FAHRENHEIT, interval)


def celsius_to_kelvin(celsius: float, interval: bool = False) -> float:
    """Convert a temperature in Celsius to Fahrenheit."""
    return convert(celsius, TEMP_CELSIUS, TEMP_KELVIN, interval)


def convert(
    temperature: float, from_unit: str, to_unit: str, interval: bool = False
) -> float:
    """Convert a temperature from one unit to another."""
    report(
        (
            "uses temperature utility. This is deprecated since 2022.10 and will "
            "stop working in Home Assistant 2023.4, it should be updated to use "
            "unit_conversion.TemperatureConverter instead"
        ),
        error_if_core=False,
    )
    if interval:
        return TemperatureConverter.convert_interval(temperature, from_unit, to_unit)
    return TemperatureConverter.convert(temperature, from_unit, to_unit)
