"""Temperature util functions."""
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT


def fahrenheit_to_celsius(fahrenheit: float) -> float:
    """Convert a Fahrenheit temperature to Celsius."""
    return (fahrenheit - 32.0) / 1.8


def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert a Celsius temperature to Fahrenheit."""
    return celsius * 1.8 + 32.0


def convert(temperature: float, from_unit: str, to_unit: str) -> (float, str):
    """Convert a temperature from one unit to another."""
    if from_unit not in [TEMP_CELSIUS, TEMP_FAHRENHEIT] or \
        to_unit not in [TEMP_CELSIUS, TEMP_FAHRENHEIT] or \
            to_unit == from_unit:
        # If no need or unknown conversion, return temperature
        return temperature, from_unit

    return (
        celsius_to_fahrenheit(
            temperature) if from_unit == TEMP_CELSIUS else round(
                fahrenheit_to_celsius(temperature), 1), to_unit)
