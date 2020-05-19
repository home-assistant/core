"""The synology component."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

PLATFORMS = ["camera"]


async def async_setup(hass: HomeAssistantType, config: dict) -> bool:
    """Set up platform."""
    # TODO: import
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up config entry."""
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )
    return True
