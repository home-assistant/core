"""The syncthru component."""

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType, HomeAssistantType


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up."""
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, SENSOR_DOMAIN)
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload the config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, SENSOR_DOMAIN)
