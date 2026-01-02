"""Suez water update coordinator."""

from dataclasses import dataclass
from datetime import date, datetime
import logging

from pysuez import PySuezError, SuezClient, TelemetryMeasure

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    StatisticMeanType,
    StatisticsRow,
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CURRENCY_EURO,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_conversion import VolumeConverter

from .const import CONF_COUNTER_ID, DATA_REFRESH_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class SuezWaterAggregatedAttributes:
    """Class containing aggregated sensor extra attributes."""

    this_month_consumption: dict[str, float]
    previous_month_consumption: dict[str, float]
    last_year_overall: int
    this_year_overall: int
    history: dict[str, float]
    highest_monthly_consumption: float


@dataclass
class SuezWaterData:
    """Class used to hold all fetch data from suez api."""

    aggregated_value: float
    aggregated_attr: SuezWaterAggregatedAttributes
    price: float | None


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
        self._counter_id = self.config_entry.data[CONF_COUNTER_ID]
        self._cost_statistic_id = f"{DOMAIN}:{self._counter_id}_water_cost_statistics"
        self._water_statistic_id = (
            f"{DOMAIN}:{self._counter_id}_water_consumption_statistics"
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
        except PySuezError as err:
            raise UpdateFailed("Suez coordinator error communicating with API") from err

        price = None
        try:
            price = (await self._suez_client.get_price()).price
        except PySuezError:
            _LOGGER.debug("Failed to fetch water price", stack_info=True)

        try:
            await self._update_statistics(price)
        except PySuezError as err:
            raise UpdateFailed("Failed to update suez water statistics") from err

        _LOGGER.debug("Successfully fetched suez data")
        return SuezWaterData(
            aggregated_value=aggregated.value,
            aggregated_attr=SuezWaterAggregatedAttributes(
                this_month_consumption=map_dict(aggregated.current_month),
                previous_month_consumption=map_dict(aggregated.previous_month),
                highest_monthly_consumption=aggregated.highest_monthly_consumption,
                last_year_overall=aggregated.previous_year,
                this_year_overall=aggregated.current_year,
                history=map_dict(aggregated.history),
            ),
            price=price,
        )

    async def _update_statistics(self, current_price: float | None) -> None:
        """Update daily statistics."""
        _LOGGER.debug("Updating statistics for %s", self._water_statistic_id)

        water_last_stat = await self._get_last_stat(self._water_statistic_id)
        cost_last_stat = await self._get_last_stat(self._cost_statistic_id)
        consumption_sum = (
            water_last_stat["sum"]
            if water_last_stat and water_last_stat["sum"]
            else 0.0
        )
        cost_sum = (
            cost_last_stat["sum"] if cost_last_stat and cost_last_stat["sum"] else 0.0
        )
        last_stats = (
            datetime.fromtimestamp(water_last_stat["start"]).date()
            if water_last_stat
            else None
        )

        _LOGGER.debug(
            "Updating suez stat since %s for %s",
            str(last_stats),
            water_last_stat,
        )
        if not (
            usage := await self._suez_client.fetch_all_daily_data(
                since=last_stats,
            )
        ):
            _LOGGER.debug("No recent usage data. Skipping update")
            return
        _LOGGER.debug("fetched data: %s", len(usage))

        consumption_statistics, cost_statistics = self._build_statistics(
            current_price, consumption_sum, cost_sum, last_stats, usage
        )

        self._persist_statistics(consumption_statistics, cost_statistics)

    def _build_statistics(
        self,
        current_price: float | None,
        consumption_sum: float,
        cost_sum: float,
        last_stats: date | None,
        usage: list[TelemetryMeasure],
    ) -> tuple[list[StatisticData], list[StatisticData]]:
        """Build statistics data from fetched data."""
        consumption_statistics = []
        cost_statistics = []

        for data in usage:
            if (
                (last_stats is not None and data.date <= last_stats)
                or not data.index
                or data.volume is None
            ):
                continue
            consumption_date = dt_util.start_of_local_day(data.date)

            consumption_sum += data.volume
            consumption_statistics.append(
                StatisticData(
                    start=consumption_date,
                    state=data.volume,
                    sum=consumption_sum,
                )
            )
            if current_price is not None:
                day_cost = (data.volume / 1000) * current_price
                cost_sum += day_cost
                cost_statistics.append(
                    StatisticData(
                        start=consumption_date,
                        state=day_cost,
                        sum=cost_sum,
                    )
                )

        return consumption_statistics, cost_statistics

    def _persist_statistics(
        self,
        consumption_statistics: list[StatisticData],
        cost_statistics: list[StatisticData],
    ) -> None:
        """Persist given statistics in recorder."""
        consumption_metadata = self._get_statistics_metadata(
            id=self._water_statistic_id,
            name="Consumption",
            unit=UnitOfVolume.LITERS,
            unit_class=VolumeConverter.UNIT_CLASS,
        )

        _LOGGER.debug(
            "Adding %s statistics for %s",
            len(consumption_statistics),
            self._water_statistic_id,
        )
        async_add_external_statistics(
            self.hass, consumption_metadata, consumption_statistics
        )

        if len(cost_statistics) > 0:
            _LOGGER.debug(
                "Adding %s statistics for %s",
                len(cost_statistics),
                self._cost_statistic_id,
            )
            cost_metadata = self._get_statistics_metadata(
                id=self._cost_statistic_id,
                name="Cost",
                unit=CURRENCY_EURO,
                unit_class=None,
            )
            async_add_external_statistics(self.hass, cost_metadata, cost_statistics)

        _LOGGER.debug("Updated statistics for %s", self._water_statistic_id)

    def _get_statistics_metadata(
        self, id: str, name: str, unit: str, unit_class: str | None
    ) -> StatisticMetaData:
        """Build statistics metadata for requested configuration."""
        return StatisticMetaData(
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name=f"Suez water {name} {self._counter_id}",
            source=DOMAIN,
            statistic_id=id,
            unit_class=unit_class,
            unit_of_measurement=unit,
        )

    async def _get_last_stat(self, id: str) -> StatisticsRow | None:
        """Find last registered statistics of given id."""
        last_stat = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics, self.hass, 1, id, True, {"sum"}
        )
        return last_stat[id][0] if last_stat else None
