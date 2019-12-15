"""Solar-Log integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType


async def async_setup(hass, config):
    """Component setup, do nothing."""
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up a config entry for solarlog."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")
