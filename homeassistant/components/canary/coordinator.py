"""Provides the Canary DataUpdateCoordinator."""
from __future__ import annotations

from collections.abc import ValuesView
from datetime import timedelta
import logging

from async_timeout import timeout
from canary.api import Api
from canary.model import Entry, Location
from requests.exceptions import ConnectTimeout, HTTPError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_TYPE_ENTRY, DATA_TYPE_READING, DOMAIN
from .model import CanaryData

_LOGGER = logging.getLogger(__name__)


class CanaryDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Canary data."""

    def __init__(self, hass: HomeAssistant, *, api: Api) -> None:
        """Initialize global Canary data updater."""
        self.canary = api
        update_interval = timedelta(seconds=30)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    def _update_data(self) -> CanaryData:
        """Fetch data from Canary via sync functions."""
        locations_by_id: dict[str, Location] = {}
        readings_by_device_id: dict[str, ValuesView] = {}
        entries_by_device_id: dict[str, list[Entry]] = {}

        for location in self.canary.get_locations():
            location_id = location.location_id
            locations_by_id[location_id] = location

            for device in location.devices:
                if device.is_online:
                    readings_by_device_id[
                        device.device_id
                    ] = self.canary.get_latest_readings(device.device_id)

            entries_by_device_id = self._group_entries_by_device(location, location_id)

        return {
            "locations": locations_by_id,
            DATA_TYPE_READING: readings_by_device_id,
            DATA_TYPE_ENTRY: entries_by_device_id,
        }

    def _group_entries_by_device(
        self, location: Location, location_id: int
    ) -> dict[str, list[Entry]]:
        entries_by_device_id: dict[str, list[Entry]] = {}

        entries = self.canary.get_entries(location_id=location_id)
        for device in location.devices:
            entries_by_device_id[device.device_id] = [
                entry
                for entry in entries
                for device_uuid in entry.device_uuids
                if device.uuid == device_uuid
            ]
        return entries_by_device_id

    async def _async_update_data(self) -> CanaryData:
        """Fetch data from Canary."""

        try:
            async with timeout(15):
                return await self.hass.async_add_executor_job(self._update_data)
        except (ConnectTimeout, HTTPError) as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
