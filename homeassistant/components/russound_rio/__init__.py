"""The russound_rio component."""

import asyncio
import logging

from aiorussound import RussoundClient, RussoundTcpConnectionHandler
from aiorussound.models import CallbackType

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONNECT_TIMEOUT, DOMAIN, RUSSOUND_RIO_EXCEPTIONS

PLATFORMS = [Platform.MEDIA_PLAYER]

_LOGGER = logging.getLogger(__name__)

type RussoundConfigEntry = ConfigEntry[RussoundClient]


async def async_setup_entry(hass: HomeAssistant, entry: RussoundConfigEntry) -> bool:
    """Set up a config entry."""

    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    client = RussoundClient(RussoundTcpConnectionHandler(host, port))

    async def _connection_update_callback(
        _client: RussoundClient, _callback_type: CallbackType
    ) -> None:
        """Call when the device is notified of changes."""
        if _callback_type == CallbackType.CONNECTION:
            if _client.is_connected():
                _LOGGER.warning("Reconnected to device at %s", entry.data[CONF_HOST])
            else:
                _LOGGER.warning("Disconnected from device at %s", entry.data[CONF_HOST])

    await client.register_state_update_callbacks(_connection_update_callback)

    try:
        async with asyncio.timeout(CONNECT_TIMEOUT):
            await client.connect()
    except RUSSOUND_RIO_EXCEPTIONS as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="entry_cannot_connect",
            translation_placeholders={
                "host": host,
                "port": port,
            },
        ) from err
    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.disconnect()

    return unload_ok
