"""The netwave-camera integration."""
import logging

from homeassistant.core import HomeAssistant

from ...config_entries import ConfigEntry
from ...helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["camera"]


async def _setup_services(hass: HomeAssistant):
    """Initialize the services for NetWave."""


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the netwave-camera component."""
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up camera from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "camera")
    )
    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload camrta config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "camera")
    return True
