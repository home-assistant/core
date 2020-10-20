"""The twinkly component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType


async def async_setup(hass: HomeAssistantType, config: dict):
    """Set up the twinkly integration."""

    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry):
    """Set up entries from config flow."""

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "light")
    )
    return True
