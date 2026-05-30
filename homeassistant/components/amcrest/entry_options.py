"""Config entry option helpers for Amcrest."""

from typing import cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_BINARY_SENSORS, CONF_SENSORS, CONF_SWITCHES


def get_binary_sensor_keys(entry: ConfigEntry) -> list[str] | None:
    """Return configured binary sensor keys, or None for UI defaults."""
    if CONF_BINARY_SENSORS in entry.options:
        return cast(list[str], entry.options[CONF_BINARY_SENSORS])
    return None


def get_sensor_keys(entry: ConfigEntry) -> list[str] | None:
    """Return configured sensor keys, or None for UI defaults."""
    if CONF_SENSORS in entry.options:
        return cast(list[str], entry.options[CONF_SENSORS])
    return None


def get_switch_keys(entry: ConfigEntry) -> list[str] | None:
    """Return configured switch keys, or None for UI defaults."""
    if CONF_SWITCHES in entry.options:
        return cast(list[str], entry.options[CONF_SWITCHES])
    return None
