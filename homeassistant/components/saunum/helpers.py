"""Helper functions for Saunum Leil Sauna Control Unit integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    CONF_SAUNA_TYPE_1_NAME,
    CONF_SAUNA_TYPE_2_NAME,
    CONF_SAUNA_TYPE_3_NAME,
    DEFAULT_SAUNA_TYPE_1_NAME,
    DEFAULT_SAUNA_TYPE_2_NAME,
    DEFAULT_SAUNA_TYPE_3_NAME,
    DEFAULT_TEMPERATURE_C,
    DEFAULT_TEMPERATURE_F,
    MAX_TEMPERATURE_C,
    MAX_TEMPERATURE_F,
    MIN_TEMPERATURE_C,
    MIN_TEMPERATURE_F,
    SAUNA_TYPE_1,
    SAUNA_TYPE_2,
    SAUNA_TYPE_3,
)


def convert_temperature(
    value: float | None, from_unit: str, to_unit: str
) -> float | None:
    """Convert temperature between units."""
    if value is None:
        # No temperature provided; nothing to convert.
        return None

    if from_unit == to_unit:
        # Units match; short-circuit without calling converter.
        return value

    # Perform conversion through HA's TemperatureConverter.
    return TemperatureConverter.convert(value, from_unit, to_unit)


def get_temperature_range_for_unit(unit: str) -> tuple[float, float, float]:
    """Get temperature range (min, max, default) for the specified unit."""
    if unit == UnitOfTemperature.FAHRENHEIT:
        return MIN_TEMPERATURE_F, MAX_TEMPERATURE_F, DEFAULT_TEMPERATURE_F
    return MIN_TEMPERATURE_C, MAX_TEMPERATURE_C, DEFAULT_TEMPERATURE_C


def get_temperature_unit(hass: HomeAssistant) -> str:
    """Get temperature unit from Home Assistant configuration."""
    return hass.config.units.temperature_unit


def get_custom_sauna_type_names(config_entry: ConfigEntry) -> dict[int, str]:
    """Get custom sauna type names from config entry options."""
    return {
        SAUNA_TYPE_1: config_entry.options.get(
            CONF_SAUNA_TYPE_1_NAME, DEFAULT_SAUNA_TYPE_1_NAME
        ),
        SAUNA_TYPE_2: config_entry.options.get(
            CONF_SAUNA_TYPE_2_NAME, DEFAULT_SAUNA_TYPE_2_NAME
        ),
        SAUNA_TYPE_3: config_entry.options.get(
            CONF_SAUNA_TYPE_3_NAME, DEFAULT_SAUNA_TYPE_3_NAME
        ),
    }
