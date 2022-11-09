"""The kodi component."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant

from .connection_manager import KodiConnectionManager
from .const import DATA_CONNECTION, DATA_REMOVE_LISTENER, DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.MEDIA_PLAYER, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kodi from a config entry."""
    connman = KodiConnectionManager(hass, entry)
    if not await connman.connect():
        return False

    async def _close(event):  # pylint: disable=unused-argument
        await connman.remove()

    remove_stop_listener = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CONNECTION: connman,
        DATA_REMOVE_LISTENER: remove_stop_listener,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data[DATA_CONNECTION].remove()
        data[DATA_REMOVE_LISTENER]()

    return unload_ok
