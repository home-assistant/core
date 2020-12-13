"""The kodi component."""

import asyncio
import logging

from pykodi import CannotConnectError, InvalidAuthError, Kodi, get_kodi_connection

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_WS_PORT,
    DATA_CONNECTION,
    DATA_KODI,
    DATA_REMOVE_LISTENER,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["media_player"]


async def async_setup(hass, config):
    """Set up the Kodi integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Kodi from a config entry."""
    conn = get_kodi_connection(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_WS_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_SSL],
        session=async_get_clientsession(hass),
    )

    kodi = Kodi(conn)

    try:
        await conn.connect()
    except CannotConnectError:
        pass
    except InvalidAuthError as error:
        _LOGGER.error(
            "Login to %s failed: [%s]",
            entry.data[CONF_HOST],
            error,
        )
        return False

    async def _close(event):
        await conn.close()

    remove_stop_listener = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close)

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CONNECTION: conn,
        DATA_KODI: kodi,
        DATA_REMOVE_LISTENER: remove_stop_listener,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data[DATA_CONNECTION].close()
        data[DATA_REMOVE_LISTENER]()

    return unload_ok
