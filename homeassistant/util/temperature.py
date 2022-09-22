"""Temperature util functions."""
from homeassistant.const import (  # pylint: disable=unused-import # noqa: F401
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
    report(
        "uses temperature utility. This is deprecated since 2022.10 and will "
        "stop working in Home Assistant 2022.4, it should be updated to use "
        "unit_conversion.TemperatureConverter instead",
        error_if_core=False,
    )
    return TemperatureConverter.fahrenheit_to_celsius(fahrenheit, interval)


def kelvin_to_celsius(kelvin: float, interval: bool = False) -> float:
    """Convert a temperature in Kelvin to Celsius."""
    report(
        "uses temperature utility. This is deprecated since 2022.10 and will "
        "stop working in Home Assistant 2022.4, it should be updated to use "
        "unit_conversion.TemperatureConverter instead",
        error_if_core=False,
    )
    return TemperatureConverter.kelvin_to_celsius(kelvin, interval)


def celsius_to_fahrenheit(celsius: float, interval: bool = False) -> float:
    """Convert a temperature in Celsius to Fahrenheit."""
    report(
        "uses temperature utility. This is deprecated since 2022.10 and will "
        "stop working in Home Assistant 2022.4, it should be updated to use "
        "unit_conversion.TemperatureConverter instead",
        error_if_core=False,
    )
    return TemperatureConverter.celsius_to_fahrenheit(celsius, interval)


def celsius_to_kelvin(celsius: float, interval: bool = False) -> float:
    """Convert a temperature in Celsius to Fahrenheit."""
    report(
        "uses temperature utility. This is deprecated since 2022.10 and will "
        "stop working in Home Assistant 2022.4, it should be updated to use "
        "unit_conversion.TemperatureConverter instead",
        error_if_core=False,
    )
    return TemperatureConverter.celsius_to_kelvin(celsius, interval)


def convert(
    temperature: float, from_unit: str, to_unit: str, interval: bool = False
) -> float:
    """Convert a temperature from one unit to another."""
    report(
        "uses temperature utility. This is deprecated since 2022.10 and will "
        "stop working in Home Assistant 2022.4, it should be updated to use "
        "unit_conversion.TemperatureConverter instead",
        error_if_core=False,
    )
    return TemperatureConverter.convert(
        temperature, from_unit, to_unit, interval=interval
    )
