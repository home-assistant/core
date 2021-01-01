"""Support for IamMeter Devices."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN


async def async_setup(hass, config):
    """Component setup, do nothing."""
    config = config.get(DOMAIN)
    if config is None:
        hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up a config entry for iammeter."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True


async def async_unload_entry(hass, _):
    """Unload a config entry."""
    return True
