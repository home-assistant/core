"""Suez water update coordinator."""

import asyncio
from datetime import datetime, timedelta
from typing import Any

from pysuez import SuezClient
from pysuez.client import PySuezError

from homeassistant.core import _LOGGER, HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN


class AggregatedSensorData:
    """Hold suez water aggregated sensor data."""

    def __init__(
        self,
        value: float,
        currentMonth: Any,
        previousMonth: Any,
        previousYear: Any,
        currentYear: Any,
        history: Any,
        highestMonthlyConsumption: Any,
        attribution: str,
    ) -> None:
        """Create aggregated sensor data."""
        self.value = value
        self.currentMonth = currentMonth
        self.previousMonth = previousMonth
        self.previousYear = previousYear
        self.currentYear = currentYear
        self.history = history
        self.highestMonthlyConsumption = highestMonthlyConsumption
        self.attribution = attribution


class SuezWaterCoordinator(DataUpdateCoordinator):
    """Suez water coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: SuezClient,
        counter_id: int,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=12),
            always_update=True,
        )
        self._sync_client = client
        self._counter_id = counter_id
        self.aggregated_data: None | AggregatedSensorData = None

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint."""
        try:
            async with asyncio.timeout(30):
                await self._update_aggregated_historical_sensor()
                _LOGGER.debug("Suez sensors data update completed")
            return {"update": datetime.now()}
        except PySuezError as err:
            raise UpdateFailed(
                f"Suez coordinator error communicating with API: {err}"
            ) from err

    async def _update_aggregated_historical_sensor(self) -> None:
        """Fetch last known consumption and aggregated statistics."""
        await self.hass.async_add_executor_job(self._fetch_data)

    def _fetch_data(self) -> None:
        """Fetch latest data from Suez."""
        try:
            self._sync_client.update()
            currentMonth = {}
            for item in self._sync_client.attributes["thisMonthConsumption"]:
                currentMonth[item] = self._sync_client.attributes[
                    "thisMonthConsumption"
                ][item]
            previousMonth = {}
            for item in self._sync_client.attributes["previousMonthConsumption"]:
                previousMonth[item] = self._sync_client.attributes[
                    "previousMonthConsumption"
                ][item]
            highestMonthlyConsumption = self._sync_client.attributes[
                "highestMonthlyConsumption"
            ]
            previousYear = self._sync_client.attributes["lastYearOverAll"]
            currentYear = self._sync_client.attributes["thisYearOverAll"]
            history = {}
            for item in self._sync_client.attributes["history"]:
                history[item] = self._sync_client.attributes["history"][item]
            _LOGGER.debug("Retrieved consumption: " + str(self._sync_client.state))
            self.aggregated_data = AggregatedSensorData(
                self._sync_client.state,
                currentMonth,
                previousMonth,
                previousYear,
                currentYear,
                history,
                highestMonthlyConsumption,
                self._sync_client.attributes["attribution"],
            )

        except PySuezError as err:
            _LOGGER.error("Unable to fetch data", err)
