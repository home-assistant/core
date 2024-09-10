"""The Cambridge Audio integration."""

from __future__ import annotations

import asyncio

from aiostreammagic import StreamMagicClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONNECT_TIMEOUT, STREAM_MAGIC_EXCEPTIONS

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

type CambridgeAudioConfigEntry = ConfigEntry[StreamMagicClient]


async def async_setup_entry(
    hass: HomeAssistant, entry: CambridgeAudioConfigEntry
) -> bool:
    """Set up Cambridge Audio integration from a config entry."""

    client = StreamMagicClient(entry.data[CONF_HOST])

    try:
        async with asyncio.timeout(CONNECT_TIMEOUT):
            await client.connect()
    except STREAM_MAGIC_EXCEPTIONS as err:
        raise ConfigEntryNotReady(f"Error while connecting to {client.host}") from err
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
