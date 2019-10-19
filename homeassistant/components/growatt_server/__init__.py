"""The Growatt server PV inverter sensor integration."""
from homeassistant import config_entries
from homeassistant.helpers.typing import HomeAssistantType


async def async_setup(hass, config):
    """Set up this integration."""
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: config_entries.ConfigEntry):
    """Load the saved entities."""

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")
