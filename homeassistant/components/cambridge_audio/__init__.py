"""The Cambridge Audio integration."""

from __future__ import annotations

from aiostreammagic import StreamMagicClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

type CambridgeAudioConfigEntry = ConfigEntry[StreamMagicClient]


async def async_setup_entry(
    hass: HomeAssistant, entry: CambridgeAudioConfigEntry
) -> bool:
    """Set up Cambridge Audio integration from a config entry."""

    client = StreamMagicClient(
        entry.data[CONF_HOST],
    )

    try:
        await client.connect()
    except:
        raise ConfigEntryNotReady("Not ready")

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: CambridgeAudioConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
