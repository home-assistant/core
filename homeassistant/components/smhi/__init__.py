"""Support for the Swedish weather institute weather service."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

# Have to import for config_flow to work even if they are not used here
from .config_flow import smhi_locations  # noqa: F401
from .const import DOMAIN  # noqa: F401

DEFAULT_NAME = "smhi"

PLATFORMS = ["weather"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SMHI forecast as config entry."""
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
