"""SmartTub integration."""
import logging

from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, SMARTTUB_CONTROLLER, UNSUB_UPDATE_LISTENER
from .controller import SmartTubController

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate"]


async def async_setup(hass, _config):
    """Set up smarttub component."""

    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass, entry):
    """Set up a smarttub config entry."""

    controller = SmartTubController(hass)
    hass.data[DOMAIN][entry.unique_id] = {
        SMARTTUB_CONTROLLER: controller,
    }

    if not await controller.async_setup_entry(entry):
        raise ConfigEntryNotReady

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    hass.data[DOMAIN][entry.unique_id][
        UNSUB_UPDATE_LISTENER
    ] = entry.add_update_listener(async_update_options)

    return True


async def async_unload_entry(hass, entry):
    """Remove a smarttub config entry."""
    for platform in PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(entry, platform)

    controller = hass.data[DOMAIN][entry.unique_id][SMARTTUB_CONTROLLER]
    await controller.async_unload_entry(entry)
    hass.data[DOMAIN].pop(entry.unique_id)

    return True


async def async_update_options(hass, config_entry):
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)
