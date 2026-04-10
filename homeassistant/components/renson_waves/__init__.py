"""Renson WAVES integration."""

from __future__ import annotations

import asyncio
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import RensonWavesClient
from .const import DOMAIN as DOMAIN
from .coordinator import RensonWavesCoordinator

PLATFORMS: Final[list[Platform]] = [Platform.BINARY_SENSOR, Platform.SENSOR]

type RensonWavesConfigEntry = ConfigEntry[RensonWavesCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: RensonWavesConfigEntry) -> bool:
    """Set up Renson WAVES integration."""
    host: str = entry.data[CONF_HOST]
    port: int = entry.data[CONF_PORT]

    session = async_get_clientsession(hass)
    client = RensonWavesClient(host, port, session)

    coordinator = RensonWavesCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: RensonWavesConfigEntry
) -> bool:
    """Unload Renson WAVES integration."""
    return all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
