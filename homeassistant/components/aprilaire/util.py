"""Utililities for the Aprilaire integration."""

from math import ceil, floor

from homeassistant.const import UnitOfTemperature
from homeassistant.util.unit_conversion import TemperatureConverter


def convert_temperature_if_needed(
    temperature_unit: UnitOfTemperature, temperature: float
) -> float:
    """Convert a temperature manually to correct rounding errors."""

    if temperature is not None and temperature_unit == UnitOfTemperature.FAHRENHEIT:
        raw_fahrenheit = TemperatureConverter.convert(
            temperature, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT
        )

        if raw_fahrenheit >= 0:
            temperature = floor(raw_fahrenheit + 0.5)
        else:
            temperature = ceil(raw_fahrenheit - 0.5)

    return temperature
