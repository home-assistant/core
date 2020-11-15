"""The Raspberry Pi Power Supply Checker integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Raspberry Pi Power Supply Checker component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Raspberry Pi Power Supply Checker from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "binary_sensor")
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, "binary_sensor")
