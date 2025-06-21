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

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

type EafmConfigEntry = ConfigEntry[EafmCoordinator]


def _get_measures(station_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Force measure key to always be a list."""
    if "measures" not in station_data:
        return []
    if isinstance(station_data["measures"], dict):
        return [station_data["measures"]]
    return station_data["measures"]


class EafmCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Class to manage fetching UK Flood Monitoring data."""

    def __init__(self, hass: HomeAssistant, entry: EafmConfigEntry) -> None:
        """Initialize."""
        self._station_key = entry.data["station"]
        self._session = async_get_clientsession(hass=hass)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="sensor",
            update_interval=timedelta(seconds=15 * 60),
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch the latest data from the source."""
        # DataUpdateCoordinator will handle aiohttp ClientErrors and timeouts
        async with asyncio.timeout(30):
            data = await get_station(self._session, self._station_key)

        measures = _get_measures(data)
        # Turn data.measures into a dict rather than a list so easier for entities to
        # find themselves.
        data["measures"] = {measure["@id"]: measure for measure in measures}
        return data
