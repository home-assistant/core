"""Utililities for the Aprilaire integration."""

from math import ceil, floor

from homeassistant.const import UnitOfTemperature
from homeassistant.util.unit_conversion import TemperatureConverter


def convert_temperature_if_needed(
    temperature_unit: UnitOfTemperature, temperature: float | None
) -> float | None:
    """Convert a temperature manually to correct rounding errors.

    This is due to the fact that the rounding in Home Assistant does not match the rounding
    that is performed on the device. Relying on the Home Assistant rounding results in an
    off-by-one issue. This code uses the current temperature unit for the sensor and rounds
    according to the Aprilaire conventions to match what is displayed on the device.
    """

    if temperature is not None and temperature_unit == UnitOfTemperature.FAHRENHEIT:
        raw_fahrenheit = TemperatureConverter.convert(
            temperature, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT
        )

        if raw_fahrenheit >= 0:
            temperature = floor(raw_fahrenheit + 0.5)
        else:
            temperature = ceil(raw_fahrenheit - 0.5)

    return temperature
