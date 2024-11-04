"""Suez water update coordinator."""

import asyncio
from dataclasses import dataclass
from datetime import date

from pysuez import SuezClient
from pysuez.client import PySuezError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import _LOGGER, HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_COUNTER_ID, DATA_REFRESH_INTERVAL, DOMAIN


@dataclass
class AggregatedSensorData:
    """Hold suez water aggregated sensor data."""

    value: float
    current_month: dict[date, float]
    previous_month: dict[date, float]
    previous_year: dict[str, float]
    current_year: dict[str, float]
    history: dict[date, float]
    highest_monthly_consumption: float
    attribution: str


class SuezWaterCoordinator(DataUpdateCoordinator[AggregatedSensorData]):
    """Suez water coordinator."""

    _sync_client: SuezClient
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize suez water coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DATA_REFRESH_INTERVAL,
            always_update=True,
            config_entry=config_entry,
        )

    async def _async_setup(self) -> None:
        self._sync_client = await self.hass.async_add_executor_job(self._get_client)

    async def _async_update_data(self) -> AggregatedSensorData:
        """Fetch data from API endpoint."""
        async with asyncio.timeout(30):
            return await self.hass.async_add_executor_job(self._fetch_data)

    def _fetch_data(self) -> AggregatedSensorData:
        """Fetch latest data from Suez."""
        try:
            self._sync_client.update()
        except PySuezError as err:
            raise UpdateFailed(
                f"Suez coordinator error communicating with API: {err}"
            ) from err
        current_month = {}
        for item in self._sync_client.attributes["thisMonthConsumption"]:
            current_month[item] = self._sync_client.attributes["thisMonthConsumption"][
                item
            ]
        previous_month = {}
        for item in self._sync_client.attributes["previousMonthConsumption"]:
            previous_month[item] = self._sync_client.attributes[
                "previousMonthConsumption"
            ][item]
        highest_monthly_consumption = self._sync_client.attributes[
            "highestMonthlyConsumption"
        ]
        previous_year = self._sync_client.attributes["lastYearOverAll"]
        current_year = self._sync_client.attributes["thisYearOverAll"]
        history = {}
        for item in self._sync_client.attributes["history"]:
            history[item] = self._sync_client.attributes["history"][item]
        _LOGGER.debug("Retrieved consumption: " + str(self._sync_client.state))
        return AggregatedSensorData(
            self._sync_client.state,
            current_month,
            previous_month,
            previous_year,
            current_year,
            history,
            highest_monthly_consumption,
            self._sync_client.attributes["attribution"],
        )

    def _get_client(self) -> SuezClient:
        try:
            client = SuezClient(
                username=self.config_entry.data[CONF_USERNAME],
                password=self.config_entry.data[CONF_PASSWORD],
                counter_id=self.config_entry.data[CONF_COUNTER_ID],
                provider=None,
            )
            if not client.check_credentials():
                raise ConfigEntryError
        except PySuezError as ex:
            raise ConfigEntryNotReady from ex
        return client
