"""The songpal component."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config) -> bool:
    """Set up songpal environment."""
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up songpal media player."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "media_player")
    )
    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload songpal media player."""
    return await hass.config_entries.async_forward_entry_unload(entry, "media_player")
