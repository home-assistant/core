"""The Leneda coordinator."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
import re
from typing import Any, cast

from leneda import LenedaClient
from leneda.exceptions import UnauthorizedException

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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_API_TOKEN,
    CONF_ENERGY_ID,
    CONF_METERING_POINTS,
    DOMAIN,
    SCAN_INTERVAL,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


def _create_statistic_id(metering_point: str, obis: str) -> str:
    """Create a valid statistic ID from metering point and OBIS code."""
    # Convert to lowercase and replace any non-alphanumeric characters with underscore
    clean_mp = re.sub(r"[^a-z0-9]", "_", metering_point.lower())
    clean_obis = re.sub(r"[^a-z0-9]", "_", obis.lower())
    statistic_id = f"{DOMAIN}:{clean_mp}_{clean_obis}"
    _LOGGER.debug(
        "Created statistic ID: %s from metering_point: %s, obis: %s",
        statistic_id,
        metering_point,
        obis,
    )
    return statistic_id


class LenedaCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Handle fetching Leneda data, updating sensors and inserting statistics."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the data handler."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = LenedaClient(
            api_key=config_entry.data[CONF_API_TOKEN],
            energy_id=config_entry.data[CONF_ENERGY_ID],
        )
        self.metering_points = config_entry.data[CONF_METERING_POINTS]
        self.selected_sensors = config_entry.options.get("selected_sensors", {})
        _LOGGER.debug(
            "Initialized coordinator with %s metering points and selected sensors: %s",
            len(self.metering_points),
            self.selected_sensors,
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from Leneda API and update statistics."""
        _LOGGER.debug("Starting data update")
        data = {}
        for metering_point in self.metering_points:
            _LOGGER.debug("Processing metering point: %s", metering_point)
            meter_data: dict[str, Any] = {"values": {}}
            try:
                # Only fetch data for sensors the user enabled
                sensor_types = self.selected_sensors.get(
                    metering_point, list(SENSOR_TYPES.keys())
                )
                _LOGGER.debug(
                    "Selected sensor types for %s: %s", metering_point, sensor_types
                )

                for sensor_type in sensor_types:
                    cfg = SENSOR_TYPES.get(sensor_type)
                    if not cfg:
                        _LOGGER.error(
                            "Unknown sensor type %s for %s",
                            sensor_type,
                            metering_point,
                        )
                        continue
                    obis = cfg["obis_code"]
                    _LOGGER.debug(
                        "Processing sensor type %s with OBIS code %s", sensor_type, obis
                    )

                    await self._update_statistics(metering_point, obis)
                    # Get current total for sensor
                    current_total = await self._get_current_total(metering_point, obis)
                    _LOGGER.debug(
                        "Current total for %s %s: %s",
                        metering_point,
                        obis,
                        current_total,
                    )
                    meter_data["values"][obis] = current_total

            except UnauthorizedException as err:
                _LOGGER.error(
                    "Authentication error for metering point %s: %s",
                    metering_point,
                    err,
                )
                raise ConfigEntryAuthFailed("Invalid authentication") from err
            except (ConnectionError, TimeoutError, ValueError) as err:
                _LOGGER.error(
                    "Error fetching data for metering point %s: %s", metering_point, err
                )

            data[metering_point] = meter_data
            _LOGGER.debug("Completed processing metering point %s", metering_point)

        _LOGGER.debug("Completed data update")
        return data

    async def _update_statistics(self, metering_point: str, obis: str) -> None:
        """Update statistics for a metering point and OBIS code."""
        statistic_id = _create_statistic_id(metering_point, obis)
        _LOGGER.debug("Updating statistics for %s", statistic_id)

        # Get last statistics to determine where to start
        last_stat = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics, self.hass, 1, statistic_id, True, set()
        )

        if not last_stat:
            _LOGGER.debug(
                "No existing statistics found for %s, starting new fetch with last 52 weeks",
                statistic_id,
            )
            start_date = datetime.now() - timedelta(
                weeks=52
            )  # Start with the last 52 weeks
        else:
            start_date = dt_util.utc_from_timestamp(last_stat[statistic_id][0]["end"])
            # Add a buffer to ensure we don't miss any data
            start_date = start_date - timedelta(days=7)
            _LOGGER.debug(
                "Found existing statistics for %s, starting new fetch from %s",
                statistic_id,
                start_date,
            )

        # API will have a lag of 1 day
        end_date = datetime.now()
        _LOGGER.debug(
            "Fetching hourly data for %s from %s to %s",
            statistic_id,
            start_date,
            end_date,
        )

        # Get hourly data
        result = await self.hass.async_add_executor_job(
            self.client.get_aggregated_metering_data,
            metering_point,
            obis,
            start_date,
            end_date,
            "Hour",
            "Accumulation",
        )
        _LOGGER.debug(
            "Successfully fetched hourly data for %s: %s",
            statistic_id,
            result.to_dict(),
        )

        if not hasattr(result, "aggregated_time_series"):
            _LOGGER.debug("No time series data found for %s", statistic_id)
            return

        _LOGGER.debug(
            "Found %s data points for %s",
            len(result.aggregated_time_series),
            statistic_id,
        )

        # Get existing statistics to avoid duplicates
        stats = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period,
            self.hass,
            start_date,
            None,
            {statistic_id},
            "hour",
            None,
            {"sum"},
        )

        last_stats_time = (
            stats[statistic_id][0]["start"] if stats and statistic_id in stats else None
        )
        last_sum = (
            float(cast(float, stats[statistic_id][0]["sum"]))
            if stats
            and statistic_id in stats
            and stats[statistic_id][0]["sum"] is not None
            else 0.0
        )
        _LOGGER.debug(
            "Last statistics time: %s, last sum: %s for %s",
            last_stats_time,
            last_sum,
            statistic_id,
        )

        statistics = []
        new_points = 0
        skipped_points = 0
        for point in result.aggregated_time_series:
            point_time = point.started_at
            if (
                last_stats_time is not None
                and point_time.timestamp() <= last_stats_time
            ):
                skipped_points += 1
                continue

            value = float(point.value)
            last_sum += value
            new_points += 1

            statistics.append(
                StatisticData(
                    start=point_time,
                    state=value,
                    sum=last_sum,
                )
            )

        _LOGGER.debug(
            "Processed %s points for %s: %s new, %s skipped",
            len(result.aggregated_time_series),
            statistic_id,
            new_points,
            skipped_points,
        )

        if statistics:
            _LOGGER.debug(
                "Adding %s new statistics for %s", len(statistics), statistic_id
            )
            async_add_external_statistics(
                self.hass,
                StatisticMetaData(
                    mean_type=StatisticMeanType.NONE,
                    has_sum=True,
                    name=f"{metering_point} {obis}",
                    source=DOMAIN,
                    statistic_id=statistic_id,
                    unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                ),
                statistics,
            )
            _LOGGER.debug("Successfully added statistics for %s", statistic_id)
        else:
            _LOGGER.debug("No new statistics to add for %s", statistic_id)

    async def _get_current_total(self, metering_point: str, obis: str) -> float | None:
        """Get current total consumption for a metering point and OBIS code."""
        current_year = datetime.now().year
        start_date = datetime(current_year, 1, 1)
        end_date = datetime.now()
        _LOGGER.debug(
            "Fetching current total for %s %s from %s to %s",
            metering_point,
            obis,
            start_date,
            end_date,
        )

        result = await self.hass.async_add_executor_job(
            self.client.get_aggregated_metering_data,
            metering_point,
            obis,
            start_date,
            end_date,
            "Infinite",
            "Accumulation",
        )
        _LOGGER.debug(
            "Successfully fetched current total for %s %s: %s",
            metering_point,
            obis,
            result.to_dict(),
        )

        if not hasattr(result, "aggregated_time_series"):
            _LOGGER.debug(
                "No time series data found for current total of %s %s",
                metering_point,
                obis,
            )
            return None

        if not result.aggregated_time_series:
            _LOGGER.debug(
                "Empty time series data found for current total of %s %s",
                metering_point,
                obis,
            )
            return None

        total = sum(float(pt.value) for pt in result.aggregated_time_series)
        _LOGGER.debug("Current total for %s %s: %s", metering_point, obis, total)
        return total
