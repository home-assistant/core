"""Temperature util functions."""

from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.frame import report

from .unit_conversion import TemperatureConverter

VALID_UNITS = TemperatureConverter.VALID_UNITS


def fahrenheit_to_celsius(fahrenheit: float, interval: bool = False) -> float:
    """Convert a temperature in Fahrenheit to Celsius."""
    return convert(
        fahrenheit, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS, interval
    )


def fahrenheit_to_kelvin(fahrenheit: float, interval: bool = False) -> float:
    """Convert a temperature in Fahrenheit to Kelvin."""
    return convert(
        fahrenheit, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.KELVIN, interval
    )


def kelvin_to_celsius(kelvin: float, interval: bool = False) -> float:
    """Convert a temperature in Kelvin to Celsius."""
    return convert(
        kelvin, UnitOfTemperature.KELVIN, UnitOfTemperature.CELSIUS, interval
    )


def kelvin_to_fahrenheit(kelvin: float, interval: bool = False) -> float:
    """Convert a temperature in Kelvin to Fahrenheit."""
    return convert(
        kelvin, UnitOfTemperature.KELVIN, UnitOfTemperature.FAHRENHEIT, interval
    )


def celsius_to_fahrenheit(celsius: float, interval: bool = False) -> float:
    """Convert a temperature in Celsius to Fahrenheit."""
    return convert(
        celsius, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT, interval
    )


def celsius_to_kelvin(celsius: float, interval: bool = False) -> float:
    """Convert a temperature in Celsius to Fahrenheit."""
    return convert(
        celsius, UnitOfTemperature.CELSIUS, UnitOfTemperature.KELVIN, interval
    )


def convert(temp: float, from_unit: str, to_unit: str, interval: bool = False) -> float:
    """Convert a temperature from one unit to another."""
    report(
        (
            "Uses temperature utility. This is deprecated since 2022.10 and will "
            "stop working in Home Assistant 2023.4, it should be updated to use "
            "unit_conversion.TemperatureConverter instead"
        ),
        error_if_core=False,
    )
    return (
        TemperatureConverter.convert_interval(temp, from_unit, to_unit)
        if interval
        else TemperatureConverter.convert(temp, from_unit, to_unit)
    )
