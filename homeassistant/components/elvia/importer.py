"""Importer for the Elvia integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, cast

from elvia import Elvia, error as ElviaError

from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.components.recorder.util import get_instance
from homeassistant.const import UnitOfEnergy
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from elvia.types.meter_value_types import MeterValueTimeSeries

    from homeassistant.core import HomeAssistant


class ElviaImporter:
    """Class to import data from Elvia."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_token: str,
        metering_point_id: str,
    ) -> None:
        """Initialize."""
        self.hass = hass
        self.client = Elvia(meter_value_token=api_token).meter_value()
        self.metering_point_id = metering_point_id

    async def _fetch_hourly_data(
        self,
        since: datetime,
        until: datetime,
    ) -> list[MeterValueTimeSeries]:
        """Fetch hourly data."""
        start_time = since.isoformat()
        end_time = until.isoformat()
        LOGGER.debug("Fetching hourly data  %s - %s", start_time, end_time)
        all_data = await self.client.get_meter_values(
            start_time=start_time,
            end_time=end_time,
            metering_point_ids=[self.metering_point_id],
        )
        return all_data["meteringpoints"][0]["metervalue"]["timeSeries"]

    async def import_meter_values(self) -> None:
        """Import meter values."""
        statistics: list[StatisticData] = []
        statistic_id = f"{DOMAIN}:{self.metering_point_id}_consumption"
        last_stats = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics,
            self.hass,
            1,
            statistic_id,
            True,
            {"sum"},
        )

        if not last_stats:
            # First time we insert 3 years of data (if available)
            hourly_data: list[MeterValueTimeSeries] = []
            until = dt_util.utcnow()
            for year in (3, 2, 1):
                try:
                    year_hours = await self._fetch_hourly_data(
                        since=until - timedelta(days=365 * year),
                        until=until - timedelta(days=365 * (year - 1)),
                    )
                except ElviaError.ElviaException:
                    # This will raise if the contract have no data for the
                    # year, we can safely ignore this
                    continue
                hourly_data.extend(year_hours)

            if hourly_data is None or len(hourly_data) == 0:
                LOGGER.error("No data available for the metering point")
                return
            last_stats_time = None
            _sum = 0.0
        else:
            try:
                hourly_data = await self._fetch_hourly_data(
                    since=dt_util.utc_from_timestamp(
                        last_stats[statistic_id][0]["end"]
                    ),
                    until=dt_util.utcnow(),
                )
            except ElviaError.ElviaException as err:
                LOGGER.error("Error fetching data: %s", err)
                return

            if (
                hourly_data is None
                or len(hourly_data) == 0
                or not hourly_data[-1]["verified"]
                or (from_time := dt_util.parse_datetime(hourly_data[0]["startTime"]))
                is None
            ):
                return

            curr_stat = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period,
                self.hass,
                from_time - timedelta(hours=1),
                None,
                {statistic_id},
                "hour",
                None,
                {"sum"},
            )
            first_stat = curr_stat[statistic_id][0]
            _sum = cast(float, first_stat["sum"])
            last_stats_time = first_stat["start"]

        last_stats_time_dt = (
            dt_util.utc_from_timestamp(last_stats_time) if last_stats_time else None
        )

        for entry in hourly_data:
            from_time = dt_util.parse_datetime(entry["startTime"])
            if from_time is None or (
                last_stats_time_dt is not None and from_time <= last_stats_time_dt
            ):
                continue

            _sum += entry["value"]

            statistics.append(
                StatisticData(start=from_time, state=entry["value"], sum=_sum)
            )

        async_add_external_statistics(
            hass=self.hass,
            metadata=StatisticMetaData(
                mean_type=StatisticMeanType.NONE,
                has_sum=True,
                name=f"{self.metering_point_id} Consumption",
                source=DOMAIN,
                statistic_id=statistic_id,
                unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            ),
            statistics=statistics,
        )
        LOGGER.debug("Imported %s statistics", len(statistics))
