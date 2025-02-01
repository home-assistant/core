"""The CO2 Signal integration."""

from __future__ import annotations

from aioelectricitymaps import ElectricityMaps

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import CO2SignalCoordinator

PLATFORMS = [Platform.SENSOR]

type CO2SignalConfigEntry = ConfigEntry[CO2SignalCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: CO2SignalConfigEntry) -> bool:
    """Set up CO2 Signal from a config entry."""
    session = async_get_clientsession(hass)
    coordinator = CO2SignalCoordinator(
        hass, ElectricityMaps(token=entry.data[CONF_API_KEY], session=session)
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CO2SignalConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
