"""The emby component."""

from __future__ import annotations

import logging

from pyemby import EmbyServer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_SSL, Platform
from homeassistant.core import HomeAssistant

_PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]
_LOGGER = logging.getLogger(__name__)

type EmbyConfigEntry = ConfigEntry[EmbyServer]


async def async_setup_entry(hass: HomeAssistant, entry: EmbyConfigEntry) -> bool:
    """Setup the Emby integration."""
    entry.runtime_data = emby = EmbyServer(
        host=entry.data[CONF_HOST],
        api_key=entry.data[CONF_API_KEY],
        port=entry.data[CONF_PORT],
        ssl=entry.data[CONF_SSL],
        loop=hass.loop,
    )

    await emby.register()
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EmbyConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.stop()
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
