"""The Energenie integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

PLATFORMS = ["switch"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Energenie component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Energenie from a config entry."""

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True
