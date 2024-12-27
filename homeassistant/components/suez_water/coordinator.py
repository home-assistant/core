"""Suez water update coordinator."""

from dataclasses import dataclass
from datetime import date

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

    this_month_consumption: dict[str, float]
    previous_month_consumption: dict[str, float]
    last_year_overall: dict[str, float]
    this_year_overall: dict[str, float]
    history: dict[str, float]
    highest_monthly_consumption: float


@dataclass
class SuezWaterData:
    """Class used to hold all fetch data from suez api."""

    aggregated_value: float
    aggregated_attr: SuezWaterAggregatedAttributes
    price: float


type SuezWaterConfigEntry = ConfigEntry[SuezWaterCoordinator]


class SuezWaterCoordinator(DataUpdateCoordinator[SuezWaterData]):
    """Suez water coordinator."""

    _suez_client: SuezClient
    config_entry: SuezWaterConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: SuezWaterConfigEntry) -> None:
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

        def map_dict(param: dict[date, float]) -> dict[str, float]:
            return {str(key): value for key, value in param.items()}

        try:
            aggregated = await self._suez_client.fetch_aggregated_data()
            data = SuezWaterData(
                aggregated_value=aggregated.value,
                aggregated_attr=SuezWaterAggregatedAttributes(
                    this_month_consumption=map_dict(aggregated.current_month),
                    previous_month_consumption=map_dict(aggregated.previous_month),
                    highest_monthly_consumption=aggregated.highest_monthly_consumption,
                    last_year_overall=aggregated.previous_year,
                    this_year_overall=aggregated.current_year,
                    history=map_dict(aggregated.history),
                ),
                price=(await self._suez_client.get_price()).price,
            )
        except PySuezError as err:
            raise UpdateFailed(f"Suez data update failed: {err}") from err
        _LOGGER.debug("Successfully fetched suez data")
        return data
