"""Anglian Water data coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pyanglianwater import AnglianWater
from pyanglianwater.exceptions import ExpiredAccessTokenError, UnknownEndpointError

from homeassistant.components.recorder import get_instance
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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import VolumeConverter

from .const import CONF_ACCOUNT_NUMBER, DOMAIN

type AnglianWaterConfigEntry = ConfigEntry[AnglianWaterUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(minutes=60)


class AnglianWaterUpdateCoordinator(DataUpdateCoordinator[None]):
    """Anglian Water data update coordinator."""

    config_entry: AnglianWaterConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: AnglianWater,
        config_entry: AnglianWaterConfigEntry,
    ) -> None:
        """Initialize update coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=config_entry,
        )
        self.api = api

    async def _async_update_data(self) -> None:
        """Update data from Anglian Water's API."""
        try:
            await self.api.update(self.config_entry.data[CONF_ACCOUNT_NUMBER])
            await self._insert_statistics()
        except (ExpiredAccessTokenError, UnknownEndpointError) as err:
            raise UpdateFailed from err

    async def _insert_statistics(self) -> None:
        """Insert statistics for water meters into Home Assistant."""
        for meter in self.api.meters.values():
            id_prefix = (
                f"{self.config_entry.data[CONF_ACCOUNT_NUMBER]}_{meter.serial_number}"
            )
            usage_statistic_id = f"{DOMAIN}:{id_prefix}_usage".lower()
            _LOGGER.debug("Updating statistics for meter %s", meter.serial_number)
            name_prefix = (
                f"Anglian Water {self.config_entry.data[CONF_ACCOUNT_NUMBER]} "
                f"{meter.serial_number}"
            )
            usage_metadata = StatisticMetaData(
                mean_type=StatisticMeanType.NONE,
                has_sum=True,
                name=f"{name_prefix} Usage",
                source=DOMAIN,
                statistic_id=usage_statistic_id,
                unit_class=VolumeConverter.UNIT_CLASS,
                unit_of_measurement=UnitOfVolume.CUBIC_METERS,
            )
            last_stat = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 1, usage_statistic_id, True, set()
            )
            if not last_stat:
                _LOGGER.debug("Updating statistics for the first time")
                usage_sum = 0.0
                last_stats_time = None
            else:
                if not meter.readings or len(meter.readings) == 0:
                    _LOGGER.debug("No recent usage statistics found, skipping update")
                    continue
                # Anglian Water stats are hourly, the read_at time is the time that the meter took the reading
                # We remove 1 hour from this so that the data is shown in the correct hour on the dashboards
                parsed_read_at = dt_util.parse_datetime(meter.readings[0]["read_at"])
                if not parsed_read_at:
                    _LOGGER.debug(
                        "Could not parse read_at time %s, skipping update",
                        meter.readings[0]["read_at"],
                    )
                    continue
                start = dt_util.as_local(parsed_read_at) - timedelta(hours=1)
                _LOGGER.debug("Getting statistics at %s", start)
                for end in (start + timedelta(seconds=1), None):
                    stats = await get_instance(self.hass).async_add_executor_job(
                        statistics_during_period,
                        self.hass,
                        start,
                        end,
                        {
                            usage_statistic_id,
                        },
                        "hour",
                        None,
                        {"sum"},
                    )
                    if stats:
                        break
                    if end:
                        _LOGGER.debug(
                            "Not found, trying to find oldest statistic after %s",
                            start,
                        )
                assert stats

                def _safe_get_sum(records: list[Any]) -> float:
                    if records and "sum" in records[0]:
                        return float(records[0]["sum"])
                    return 0.0

                usage_sum = _safe_get_sum(stats.get(usage_statistic_id, []))
                last_stats_time = stats[usage_statistic_id][0]["start"]

            usage_statistics = []

            for read in meter.readings:
                parsed_read_at = dt_util.parse_datetime(read["read_at"])
                if not parsed_read_at:
                    _LOGGER.debug(
                        "Could not parse read_at time %s, skipping reading",
                        read["read_at"],
                    )
                    continue
                start = dt_util.as_local(parsed_read_at) - timedelta(hours=1)
                if last_stats_time is not None and start.timestamp() <= last_stats_time:
                    continue
                usage_state = max(0, read["consumption"] / 1000)
                usage_sum = max(0, read["read"])
                usage_statistics.append(
                    StatisticData(
                        start=start,
                        state=usage_state,
                        sum=usage_sum,
                    )
                )
            _LOGGER.debug(
                "Adding %s statistics for %s", len(usage_statistics), usage_statistic_id
            )
            async_add_external_statistics(self.hass, usage_metadata, usage_statistics)
