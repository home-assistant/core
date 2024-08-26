"""Coordinator for Tibber sensors."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import cast

import tibber

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN as TIBBER_DOMAIN

FIVE_YEARS = 5 * 365 * 24

_LOGGER = logging.getLogger(__name__)


class TibberDataCoordinator(DataUpdateCoordinator[None]):
    """Handle Tibber data and insert statistics."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, tibber_connection: tibber.Tibber) -> None:
        """Initialize the data handler."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Tibber {tibber_connection.name}",
            update_interval=timedelta(minutes=20),
        )
        self._tibber_connection = tibber_connection

    async def _async_update_data(self) -> None:
        """Update data via API."""
        try:
            await self._tibber_connection.fetch_consumption_data_active_homes()
            await self._tibber_connection.fetch_production_data_active_homes()
            await self._insert_statistics()
        except tibber.RetryableHttpException as err:
            raise UpdateFailed(f"Error communicating with API ({err.status})") from err
        except tibber.FatalHttpException:
            # Fatal error. Reload config entry to show correct error.
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.config_entry.entry_id)
            )

    async def _insert_statistics(self) -> None:
        """Insert Tibber statistics."""
        for home in self._tibber_connection.get_homes():
            sensors: list[tuple[str, bool, str]] = []
            if home.hourly_consumption_data:
                sensors.append(("consumption", False, UnitOfEnergy.KILO_WATT_HOUR))
                sensors.append(("totalCost", False, home.currency))
            if home.hourly_production_data:
                sensors.append(("production", True, UnitOfEnergy.KILO_WATT_HOUR))
                sensors.append(("profit", True, home.currency))

            for sensor_type, is_production, unit in sensors:
                statistic_id = (
                    f"{TIBBER_DOMAIN}:energy_"
                    f"{sensor_type.lower()}_"
                    f"{home.home_id.replace('-', '')}"
                )

                last_stats = await get_instance(self.hass).async_add_executor_job(
                    get_last_statistics, self.hass, 1, statistic_id, True, set()
                )

                if not last_stats:
                    # First time we insert 5 years of data (if available)
                    hourly_data = await home.get_historic_data(
                        5 * 365 * 24, production=is_production
                    )

                    _sum = 0.0
                    last_stats_time = None
                else:
                    # hourly_consumption/production_data contains the last 30 days
                    # of consumption/production data.
                    # We update the statistics with the last 30 days
                    # of data to handle corrections in the data.
                    hourly_data = (
                        home.hourly_production_data
                        if is_production
                        else home.hourly_consumption_data
                    )

                    from_time = dt_util.parse_datetime(hourly_data[0]["from"])
                    if from_time is None:
                        continue
                    start = from_time - timedelta(hours=1)
                    stat = await get_instance(self.hass).async_add_executor_job(
                        statistics_during_period,
                        self.hass,
                        start,
                        None,
                        {statistic_id},
                        "hour",
                        None,
                        {"sum"},
                    )
                    if statistic_id in stat:
                        first_stat = stat[statistic_id][0]
                        _sum = cast(float, first_stat["sum"])
                        last_stats_time = first_stat["start"]
                    else:
                        hourly_data = await home.get_historic_data(
                            FIVE_YEARS, production=is_production
                        )
                        _sum = 0.0
                        last_stats_time = None

                statistics = []

                last_stats_time_dt = (
                    dt_util.utc_from_timestamp(last_stats_time)
                    if last_stats_time
                    else None
                )

                for data in hourly_data:
                    if data.get(sensor_type) is None:
                        continue

                    from_time = dt_util.parse_datetime(data["from"])
                    if from_time is None or (
                        last_stats_time_dt is not None
                        and from_time <= last_stats_time_dt
                    ):
                        continue

                    _sum += data[sensor_type]

                    statistics.append(
                        StatisticData(
                            start=from_time,
                            state=data[sensor_type],
                            sum=_sum,
                        )
                    )

                metadata = StatisticMetaData(
                    has_mean=False,
                    has_sum=True,
                    name=f"{home.name} {sensor_type}",
                    source=TIBBER_DOMAIN,
                    statistic_id=statistic_id,
                    unit_of_measurement=unit,
                )
                async_add_external_statistics(self.hass, metadata, statistics)
