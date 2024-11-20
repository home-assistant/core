"""UK Environment Agency Flood Monitoring Integration."""

import asyncio
from datetime import timedelta
import logging
from typing import Any

from aioeafm import get_station

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


def get_measures(station_data):
    """Force measure key to always be a list."""
    if "measures" not in station_data:
        return []
    if isinstance(station_data["measures"], dict):
        return [station_data["measures"]]
    return station_data["measures"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up flood monitoring sensors for this config entry."""
    station_key = entry.data["station"]
    session = async_get_clientsession(hass=hass)

    async def _async_update_data() -> dict[str, dict[str, Any]]:
        # DataUpdateCoordinator will handle aiohttp ClientErrors and timeouts
        async with asyncio.timeout(30):
            data = await get_station(session, station_key)

        measures = get_measures(data)
        # Turn data.measures into a dict rather than a list so easier for entities to
        # find themselves.
        data["measures"] = {measure["@id"]: measure for measure in measures}
        return data

    coordinator = DataUpdateCoordinator[dict[str, dict[str, Any]]](
        hass,
        _LOGGER,
        config_entry=entry,
        name="sensor",
        update_method=_async_update_data,
        update_interval=timedelta(seconds=15 * 60),
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload flood monitoring sensors."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
