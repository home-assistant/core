"""The flux_led component."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Flux LED/MagicLight component."""
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Flux LED/MagicLight from a config entry."""

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "light")
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""

    return await hass.config_entries.async_forward_entry_unload(entry, "light")
