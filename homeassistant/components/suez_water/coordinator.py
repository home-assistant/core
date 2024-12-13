"""Suez water update coordinator."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from pysuez import PySuezError, SuezClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import _LOGGER, HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_COUNTER_ID, DATA_REFRESH_INTERVAL, DOMAIN


@dataclass
class SuezWaterAggregatedAttributes:
    """Class containing aggregated sensor extra attributes."""

    this_month_consumption: dict[date, float]
    previous_month_consumption: dict[date, float]
    last_year_overall: dict[str, float]
    this_year_overall: dict[str, float]
    history: dict[date, float]
    highest_monthly_consumption: float


@dataclass
class SuezWaterData:
    """Class used to hold all fetch data from suez api."""

    aggregated_value: float
    aggregated_attr: Mapping[str, Any]
    price: float


class SuezWaterCoordinator(DataUpdateCoordinator[SuezWaterData]):
    """Suez water coordinator."""

    _suez_client: SuezClient
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
        self._suez_client = SuezClient(
            username=self.config_entry.data[CONF_USERNAME],
            password=self.config_entry.data[CONF_PASSWORD],
            counter_id=self.config_entry.data[CONF_COUNTER_ID],
        )
        if not await self._suez_client.check_credentials():
            raise ConfigEntryError("Invalid credentials for suez water")

    async def _async_update_data(self) -> SuezWaterData:
        """Fetch data from API endpoint."""
        try:
            aggregated = await self._suez_client.fetch_aggregated_data()
            data = SuezWaterData(
                aggregated_value=aggregated.value,
                aggregated_attr={
                    "this_month_consumption": aggregated.current_month,
                    "previous_month_consumption": aggregated.previous_month,
                    "highest_monthly_consumption": aggregated.highest_monthly_consumption,
                    "last_year_overall": aggregated.previous_year,
                    "this_year_overall": aggregated.current_year,
                    "history": aggregated.history,
                },
                price=(await self._suez_client.get_price()).price,
            )
        except PySuezError as err:
            _LOGGER.exception(err)
            raise UpdateFailed(
                f"Suez coordinator error communicating with API: {err}"
            ) from err
        _LOGGER.debug("Successfully fetched suez data")
        return data
