"""Home Assistant integration for SOLARMAN devices."""

from __future__ import annotations

from solarman_opendata.solarman import Solarman

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PLATFORMS
from .coordinator import SolarmanConfigEntry, SolarmanDeviceUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: SolarmanConfigEntry) -> bool:
    """Set up Solarman from a config entry."""
    client = Solarman(
        async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_PORT]
    )
    coordinator = SolarmanDeviceUpdateCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SolarmanConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
