"""DataUpdateCoordinator for DayBetter devices."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from daybetter_python import DayBetterClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class DayBetterCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator fetching DayBetter device data periodically."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: DayBetterClient,
        interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name="DayBetter Coordinator",
            update_interval=interval,
        )
        self._client = client

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch data from API."""
        return await self._client.fetch_sensor_data()
