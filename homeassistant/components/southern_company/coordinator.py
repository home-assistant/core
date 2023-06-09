"""Coordinator to handle southern Company connections."""
import datetime
from datetime import timedelta
import logging

import southern_company_api
from southern_company_api.exceptions import SouthernCompanyException

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SouthernCompanyCoordinator(DataUpdateCoordinator):
    """Handle Southern company data and insert statistics."""

    def __init__(
        self,
        hass: HomeAssistant,
        southern_company_connection: southern_company_api.SouthernCompanyAPI,
    ) -> None:
        """Initialize the data handler."""
        super().__init__(
            hass,
            _LOGGER,
            name="Southern Company",
            update_interval=timedelta(minutes=60),
        )
        self._southern_company_connection = southern_company_connection

    @property
    def api(self) -> southern_company_api.SouthernCompanyAPI:
        """Access the api."""
        return self._southern_company_connection

    async def _async_update_data(
        self,
    ) -> dict[str, southern_company_api.account.MonthlyUsage]:
        """Update data via API."""
        try:
            if await self._southern_company_connection.jwt is not None:
                account_month_data: dict[
                    str, southern_company_api.account.MonthlyUsage
                ] = {}
                for account in await self._southern_company_connection.accounts:
                    _LOGGER.debug("Updating sensor data for %s", account.number)
                    account_month_data[account.number] = await account.get_month_data(
                        await self._southern_company_connection.jwt
                    )
                # Note: insert statistics can be somewhat slow on first setup.
                await self._insert_statistics()
                return account_month_data
        except SouthernCompanyException as ex:
            raise UpdateFailed("Failed updating jwt token") from ex

        raise UpdateFailed("No jwt token")

    async def _insert_statistics(self) -> None:
        """Insert Southern Company statistics."""
        if await self._southern_company_connection.jwt is None:
            raise UpdateFailed("Jwt is None")
        for account in await self._southern_company_connection.accounts:
            _LOGGER.debug("Updating Statistics for %s", account.number)
            cost_statistic_id = f"{DOMAIN}:energy_" f"cost_" f"{account.number}"
            usage_statistic_id = f"{DOMAIN}:energy_" f"usage_" f"{account.number}"

            last_stats = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 1, usage_statistic_id, True, set()
            )
            if not last_stats:
                # First time we insert 1 year of data (if available)
                _LOGGER.info(
                    "Updating statistic for the first time, this may take a while"
                )
                hourly_data = await account.get_hourly_data(
                    datetime.datetime.now() - timedelta(days=365),
                    datetime.datetime.now(),
                    await self._southern_company_connection.jwt,
                )

                _cost_sum = 0.0
                _usage_sum = 0.0
                last_stats_time = None
            else:
                # hourly_consumption/production_data contains the last 30 days
                # of consumption/production data.
                # We update the statistics with the last 30 days
                # of data to handle corrections in the data.
                hourly_data = await account.get_hourly_data(
                    datetime.datetime.now() - timedelta(days=31),
                    datetime.datetime.now(),
                    await self._southern_company_connection.jwt,
                )

                from_time = hourly_data[0].time
                start = from_time - timedelta(hours=1)
                cost_stat = await get_instance(self.hass).async_add_executor_job(
                    statistics_during_period,
                    self.hass,
                    start,
                    None,
                    [cost_statistic_id],
                    "hour",
                    None,
                    {"sum"},
                )
                _cost_sum = cost_stat[cost_statistic_id][0]["sum"] or 0.0
                last_stats_time = cost_stat[cost_statistic_id][0]["start"]
                usage_stat = await get_instance(self.hass).async_add_executor_job(
                    statistics_during_period,
                    self.hass,
                    start,
                    None,
                    [usage_statistic_id],
                    "hour",
                    None,
                    {"sum"},
                )
                _usage_sum = usage_stat[usage_statistic_id][0]["sum"] or 0.0

            cost_statistics = []
            usage_statistics = []

            for data in hourly_data:
                if data.cost is None or data.usage is None:
                    continue
                from_time = data.time
                if from_time is None or (
                    last_stats_time is not None
                    and from_time.timestamp() <= last_stats_time
                ):
                    continue
                from_time = from_time.replace(minute=0, second=0, microsecond=0)
                _cost_sum += data.cost
                _usage_sum += data.usage

                cost_statistics.append(
                    StatisticData(
                        start=from_time,
                        state=data.cost,
                        sum=_cost_sum,
                    )
                )
                usage_statistics.append(
                    StatisticData(
                        start=from_time,
                        state=data.usage,
                        sum=_usage_sum,
                    )
                )

            cost_metadata = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                name=f"Southern Company {account.name} cost",
                source=DOMAIN,
                statistic_id=cost_statistic_id,
                unit_of_measurement=None,
            )
            usage_metadata = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                name=f"Southern Company {account.name} usage",
                source=DOMAIN,
                statistic_id=usage_statistic_id,
                unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            )

            async_add_external_statistics(self.hass, cost_metadata, cost_statistics)
            async_add_external_statistics(self.hass, usage_metadata, usage_statistics)
