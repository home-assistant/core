"""DataUpdateCoordinator for DayBetter devices."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .daybetter_api import DayBetterApi


class DayBetterCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator fetching DayBetter device data periodically."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: DayBetterApi,
        interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name="DayBetter Coordinator",
            update_interval=interval,
        )
        self._api = api
        self._devices: list[dict[str, Any]] = []
        self._pids: dict[str, Any] = {}

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch data from API."""
        statuses = await self._api.fetch_device_statuses()

        if not self._devices or not self._pids:
            self._devices = await self._api.fetch_devices()
            self._pids = await self._api.fetch_pids()

        sensor_devices = self._api.filter_sensor_devices(self._devices, self._pids)

        return self._api.merge_device_status(sensor_devices, statuses)
