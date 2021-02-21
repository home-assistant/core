"""SmartTub integration."""
import asyncio
import logging

from .const import DOMAIN, SMARTTUB_CONTROLLER
from .controller import SmartTubController

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate", "sensor", "switch"]


async def async_setup(hass, config):
    """Set up smarttub component."""

    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass, entry):
    """Set up a smarttub config entry."""

    controller = SmartTubController(hass)
    hass.data[DOMAIN][entry.entry_id] = {
        SMARTTUB_CONTROLLER: controller,
    }

    if not await controller.async_setup_entry(entry):
        return False

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass, entry):
    """Remove a smarttub config entry."""
    if not all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    ):
        return False

    hass.data[DOMAIN].pop(entry.entry_id)

    return True
