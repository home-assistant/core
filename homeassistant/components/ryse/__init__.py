"""The RYSE integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ryse"


PLATFORMS = [Platform.COVER]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RYSE."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


    return True
