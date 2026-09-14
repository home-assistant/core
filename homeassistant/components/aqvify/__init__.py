"""The Aqvify integration."""

import logging

from pyaqvify import AqvifyAPI

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import (
    AqvifyAggrDataCoordinator,
    AqvifyConfigEntry,
    AqvifyCoordinator,
    AqvifyRuntimeData,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AqvifyConfigEntry) -> bool:
    """Set up Aqvify from a config entry."""

    api_client = AqvifyAPI(
        entry.data[CONF_API_KEY], websession=async_get_clientsession(hass)
    )
    coordinator = AqvifyCoordinator(hass, entry, api_client)
    aggr_coordinator = AqvifyAggrDataCoordinator(hass, entry, api_client)
    entry.runtime_data = AqvifyRuntimeData(
        coordinator=coordinator,
        aggr_data_coordinator=aggr_coordinator,
    )
    await coordinator.async_config_entry_first_refresh()
    await aggr_coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AqvifyConfigEntry) -> bool:
    """Unload Aqvify config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
