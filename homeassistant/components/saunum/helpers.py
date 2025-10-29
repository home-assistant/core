"""Helper functions for Saunum Leil Sauna Control Unit integration."""

from pysaunum import MAX_TEMPERATURE, MIN_TEMPERATURE

from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import MAX_TEMPERATURE_F, MIN_TEMPERATURE_F


def convert_temperature(
    value: float | None, from_unit: str, to_unit: str
) -> float | None:
    """Convert temperature between units."""
    if value is None:
        # No temperature provided; nothing to convert.
        return None

    # Perform conversion through HA's TemperatureConverter.
    return TemperatureConverter.convert(value, from_unit, to_unit)


def get_temperature_range_for_unit(unit: str) -> tuple[float, float]:
    """Get temperature range (min, max) for the specified unit."""
    if unit == UnitOfTemperature.FAHRENHEIT:
        return MIN_TEMPERATURE_F, MAX_TEMPERATURE_F
    return MIN_TEMPERATURE, MAX_TEMPERATURE


def get_temperature_unit(hass: HomeAssistant) -> str:
    """Get temperature unit from Home Assistant configuration."""
    return hass.config.units.temperature_unit
