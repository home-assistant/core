"""Provides the Canary DataUpdateCoordinator."""
from __future__ import annotations

import asyncio
from collections.abc import ValuesView
from datetime import timedelta
import logging

from canary.api import Api
from canary.model import Location, Reading
from requests.exceptions import ConnectTimeout, HTTPError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .model import CanaryData

_LOGGER = logging.getLogger(__name__)


class CanaryDataUpdateCoordinator(DataUpdateCoordinator[CanaryData]):
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
        readings_by_device_id: dict[str, ValuesView[Reading]] = {}

        for location in self.canary.get_locations():
            location_id = location.location_id
            locations_by_id[location_id] = location

            for device in location.devices:
                if device.is_online:
                    readings_by_device_id[
                        device.device_id
                    ] = self.canary.get_latest_readings(device.device_id)

        return {
            "locations": locations_by_id,
            "readings": readings_by_device_id,
        }

    async def _async_update_data(self) -> CanaryData:
        """Fetch data from Canary."""

        try:
            async with asyncio.timeout(15):
                return await self.hass.async_add_executor_job(self._update_data)
        except (ConnectTimeout, HTTPError) as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
