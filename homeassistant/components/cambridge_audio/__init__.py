"""The Cambridge Audio integration."""

from __future__ import annotations

import asyncio
import logging

from aiostreammagic import StreamMagicClient
from aiostreammagic.models import CallbackType

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONNECT_TIMEOUT, DOMAIN, STREAM_MAGIC_EXCEPTIONS

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.SELECT, Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)

type CambridgeAudioConfigEntry = ConfigEntry[StreamMagicClient]


async def async_setup_entry(
    hass: HomeAssistant, entry: CambridgeAudioConfigEntry
) -> bool:
    """Set up Cambridge Audio integration from a config entry."""

    client = StreamMagicClient(entry.data[CONF_HOST])

    async def _connection_update_callback(
        _client: StreamMagicClient, _callback_type: CallbackType
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
    except STREAM_MAGIC_EXCEPTIONS as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="entry_cannot_connect",
            translation_placeholders={
                "host": client.host,
            },
        ) from err
    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: CambridgeAudioConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.disconnect()
    return unload_ok
