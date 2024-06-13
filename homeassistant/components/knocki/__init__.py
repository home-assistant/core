"""The Knocki integration."""

from __future__ import annotations

from dataclasses import dataclass

from knocki import KnockiClient, KnockiConnectionError, Trigger

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

PLATFORMS: list[Platform] = [Platform.EVENT]

type KnockiConfigEntry = ConfigEntry[KnockiData]


@dataclass
class KnockiData:
    """Knocki data."""

    client: KnockiClient
    triggers: list[Trigger]


async def async_setup_entry(hass: HomeAssistant, entry: KnockiConfigEntry) -> bool:
    """Set up Knocki from a config entry."""
    client = KnockiClient(
        session=async_get_clientsession(hass), token=entry.data[CONF_TOKEN]
    )

    try:
        triggers = await client.get_triggers()
    except KnockiConnectionError as exc:
        raise ConfigEntryNotReady from exc

    entry.runtime_data = KnockiData(client=client, triggers=triggers)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_create_background_task(
        hass, client.start_websocket(), "knocki-websocket"
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: KnockiConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
