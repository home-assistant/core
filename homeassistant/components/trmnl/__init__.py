"""The TRMNL integration."""

from __future__ import annotations

from trmnl import TRMNLClient

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import TRMNLConfigEntry, TRMNLCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.TIME]


async def async_setup_entry(hass: HomeAssistant, entry: TRMNLConfigEntry) -> bool:
    """Set up TRMNL from a config entry."""
    client = TRMNLClient(
        token=entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass),
    )

    coordinator = TRMNLCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TRMNLConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
