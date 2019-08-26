"""The linky component."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import callback
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_LOGGER.error("LINKY_INIT")


async def async_setup(hass, config):
    """Set up Linky sensor from legacy config file."""
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Load the saved entities."""
    _LOGGER.error("LINKY_INIT:async_setup_entry")
    hass.data.setdefault(DOMAIN, {})

    # store the info for later
    hass.data[DOMAIN][entry.entry_id] = entry

    # TODO: also add sensors directly after adding the integration, but how ?

    @callback
    def async_start(_):
        """Load the entry after the start event."""
        _LOGGER.error("LINKY_INIT:async_start")
        for eid in hass.data[DOMAIN]:
            entry = hass.data[DOMAIN][eid]
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, "sensor")
            )
        hass.data[DOMAIN] = {}

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, async_start)

    return True
