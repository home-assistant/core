"""The IOmeter integration."""

from __future__ import annotations

from iometer import IOmeterClient, IOmeterConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import IOmeterConfigEntry, IOMeterCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: IOmeterConfigEntry) -> bool:
    """Set up IOmeter from a config entry."""

    host = entry.data[CONF_HOST]
    session = async_get_clientsession(hass)
    client = IOmeterClient(host=host, session=session)
    try:
        await client.get_current_status()
    except IOmeterConnectionError as err:
        raise ConfigEntryNotReady from err

    coordinator = IOMeterCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
