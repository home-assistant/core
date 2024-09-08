"""The Cambridge Audio integration."""

from __future__ import annotations

from aiostreammagic import StreamMagicClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import CambridgeAudioCoordinator

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

type CambridgeAudioConfigEntry = ConfigEntry[CambridgeAudioCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: CambridgeAudioConfigEntry
) -> bool:
    """Set up Cambridge Audio integration from a config entry."""

    client = StreamMagicClient(
        entry.data[CONF_HOST], session=async_get_clientsession(hass)
    )

    coordinator = CambridgeAudioCoordinator(hass, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: CambridgeAudioConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
