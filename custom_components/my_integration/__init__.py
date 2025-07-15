"""This module is for setting up the custom integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (ConfigEntry): The config entry containing the integration configuration.

    Returns:
        bool: True if the setup is successful, False otherwise.
    """
    hass.config_entries.async_setup_platforms(entry, [])
    return True
