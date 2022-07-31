"""Temperature util functions."""
from homeassistant.const import (
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TEMP_KELVIN,
    TEMPERATURE,
    UNIT_NOT_RECOGNIZED_TEMPLATE,
)

VALID_UNITS: tuple[str, ...] = (
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TEMP_KELVIN,
)


def fahrenheit_to_celsius(fahrenheit: float, interval: bool = False) -> float:
    """Convert a temperature in Fahrenheit to Celsius."""
    if interval:
        return fahrenheit / 1.8
    return (fahrenheit - 32.0) / 1.8


def kelvin_to_celsius(kelvin: float, interval: bool = False) -> float:
    """Convert a temperature in Kelvin to Celsius."""
    if interval:
        return kelvin
    return kelvin - 273.15


def celsius_to_fahrenheit(celsius: float, interval: bool = False) -> float:
    """Convert a temperature in Celsius to Fahrenheit."""
    if interval:
        return celsius * 1.8
    return celsius * 1.8 + 32.0


def celsius_to_kelvin(celsius: float, interval: bool = False) -> float:
    """Convert a temperature in Celsius to Fahrenheit."""
    if interval:
        return celsius
    return celsius + 273.15


def convert(
    temperature: float, from_unit: str, to_unit: str, interval: bool = False
) -> float:
    """Convert a temperature from one unit to another."""
    if from_unit not in (TEMP_CELSIUS, TEMP_FAHRENHEIT, TEMP_KELVIN):
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(from_unit, TEMPERATURE))
    if to_unit not in (TEMP_CELSIUS, TEMP_FAHRENHEIT, TEMP_KELVIN):
        raise ValueError(UNIT_NOT_RECOGNIZED_TEMPLATE.format(to_unit, TEMPERATURE))

    if from_unit == to_unit:
        return temperature

    if from_unit == TEMP_CELSIUS:
        if to_unit == TEMP_FAHRENHEIT:
            return celsius_to_fahrenheit(temperature, interval)
        # kelvin
        return celsius_to_kelvin(temperature, interval)

    if from_unit == TEMP_FAHRENHEIT:
        if to_unit == TEMP_CELSIUS:
            return fahrenheit_to_celsius(temperature, interval)
        # kelvin
        return celsius_to_kelvin(fahrenheit_to_celsius(temperature, interval), interval)

    # from_unit == kelvin
    if to_unit == TEMP_CELSIUS:
        return kelvin_to_celsius(temperature, interval)
    # fahrenheit
    return celsius_to_fahrenheit(kelvin_to_celsius(temperature, interval), interval)
