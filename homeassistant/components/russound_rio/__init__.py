"""The russound_rio component."""

import asyncio
import logging

from aiorussound import Russound

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONNECT_TIMEOUT, RUSSOUND_RIO_EXCEPTIONS

PLATFORMS = [Platform.MEDIA_PLAYER]

_LOGGER = logging.getLogger(__name__)

type RussoundConfigEntry = ConfigEntry[Russound]


async def async_setup_entry(hass: HomeAssistant, entry: RussoundConfigEntry) -> bool:
    """Set up a config entry."""

    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    russ = Russound(hass.loop, host, port)

    @callback
    def is_connected_updated(connected: bool) -> None:
        if connected:
            _LOGGER.warning("Reconnected to controller at %s:%s", host, port)
        else:
            _LOGGER.warning(
                "Disconnected from controller at %s:%s",
                host,
                port,
            )

    russ.add_connection_callback(is_connected_updated)

    try:
        async with asyncio.timeout(CONNECT_TIMEOUT):
            await russ.connect()
    except RUSSOUND_RIO_EXCEPTIONS as err:
        raise ConfigEntryNotReady(f"Error while connecting to {host}:{port}") from err

    entry.runtime_data = russ

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.close()

    return unload_ok
