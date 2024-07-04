"""The russound_rio component."""

import asyncio
import logging

from russound_rio import Russound

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import DOMAIN, RUSSOUND_RIO_EXCEPTIONS

PLATFORMS = [Platform.MEDIA_PLAYER]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""

    russ = Russound(hass.loop, entry.data[CONF_HOST], entry.data[CONF_PORT])

    try:
        async with asyncio.timeout(5):
            await russ.connect()
    except RUSSOUND_RIO_EXCEPTIONS as err:
        raise ConfigEntryError(err) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = russ

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
