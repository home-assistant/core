"""Utility functions used by the Electrolux integration."""

from homeassistant.const import UnitOfTemperature
from homeassistant.util.unit_conversion import TemperatureConverter


def round_to_valid_step(value: float, minimum: float, step: float) -> float:
    """Utility function for rounding a value to the closest multiple of a step."""
    return round((value - minimum) / step) * step + minimum


def convert_between_units_none_safe(
    value: float | None, from_unit: UnitOfTemperature, to_unit: UnitOfTemperature
) -> float | None:
    """Convert a value between different units."""
    if value is None:
        return None
    return TemperatureConverter.convert(value, from_unit, to_unit)


def convert_to_snake_case(x: str) -> str:
    """Converts a string to snake case."""
    lower_case = x.lower()
    return "".join([_convert_char_to_snake_case(char) for char in lower_case])


def _convert_char_to_snake_case(char: str) -> str:
    if char.isspace():
        return "_"
    return char
