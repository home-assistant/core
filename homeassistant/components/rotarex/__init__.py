"""The Rotarex integration."""

from __future__ import annotations

from typing import Final, cast

from rotarex_dimes_srg_api import RotarexApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import RotarexDataUpdateCoordinator

PLATFORMS: Final = [Platform.SENSOR]

type RotarexConfigEntry = ConfigEntry[RotarexDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: RotarexConfigEntry) -> bool:
    """Set up Rotarex from a config entry."""
    session = async_get_clientsession(hass)

    api = RotarexApi(session)
    coordinator = RotarexDataUpdateCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RotarexConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
