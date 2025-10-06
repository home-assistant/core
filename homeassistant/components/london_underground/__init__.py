"""The london_underground component."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN as DOMAIN
from .coordinator import LondonTubeCoordinator, TubeData

PLATFORMS: list[Platform] = [Platform.SENSOR]

type LondonUndergroundConfigEntry = ConfigEntry[LondonTubeCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: LondonUndergroundConfigEntry
) -> bool:
    """Set up London Underground from a config entry."""

    session = async_get_clientsession(hass)
    data = TubeData(session)
    coordinator = LondonTubeCoordinator(hass, data, config_entry=entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    # Forward the setup to the sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: LondonUndergroundConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
