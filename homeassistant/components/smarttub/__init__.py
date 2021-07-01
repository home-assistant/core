"""SmartTub integration."""
import logging

from .const import DOMAIN, SMARTTUB_CONTROLLER
from .controller import SmartTubController

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "climate", "light", "sensor", "switch"]


async def async_setup_entry(hass, entry):
    """Set up a smarttub config entry."""

    controller = SmartTubController(hass)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        SMARTTUB_CONTROLLER: controller,
    }

    if not await controller.async_setup_entry(entry):
        return False

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass, entry):
    """Remove a smarttub config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
