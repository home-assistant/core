"""Provides the data update coordinator for SolarEdge Modules."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
import logging
from typing import Any

from solaredge_web import EnergyData, SolarEdgeWeb, TimeUnit

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
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import CONF_SITE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

type SolarEdgeOptimizersConfigEntry = ConfigEntry[SolarEdgeOptimizersCoordinator]


class SolarEdgeOptimizersCoordinator(DataUpdateCoordinator[None]):
    """Handle fetching SolarEdge Modules data and inserting statistics."""

    config_entry: SolarEdgeOptimizersConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SolarEdgeOptimizersConfigEntry,
    ) -> None:
        """Initialize the data handler."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="SolarEdge Modules",
            # API refreshes every 15 minutes, but since we only have statistics
            # and no sensors, refresh every 12h.
            update_interval=timedelta(hours=12),
        )
        self.api = SolarEdgeWeb(
            username=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
            site_id=config_entry.data[CONF_SITE_ID],
            session=aiohttp_client.async_get_clientsession(hass),
        )
        self.site_id = config_entry.data[CONF_SITE_ID]
        self.title = config_entry.title

        @callback
        def _dummy_listener() -> None:
            pass

        # Force the coordinator to periodically update by registering a listener.
        # Needed because there are no sensors added.
        self.async_add_listener(_dummy_listener)

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint and update statistics."""
        equipment: dict[int, dict[str, Any]] = await self.api.async_get_equipment()
        # We fetch last week's data from the API and refresh every 12h so we overwrite recent
        # statistics. This is intended to allow adding any corrected/updated data from the API.
        energy_data_list: list[EnergyData] = await self.api.async_get_energy_data(
            TimeUnit.WEEK
        )
        if not energy_data_list:
            _LOGGER.warning(
                "No data received from SolarEdge API for site: %s", self.site_id
            )
            return
        last_sums = await self._async_get_last_sums(
            equipment.keys(),
            energy_data_list[0].start_time.replace(
                tzinfo=dt_util.get_default_time_zone()
            ),
        )
        for equipment_id, equipment_data in equipment.items():
            display_name = equipment_data.get(
                "displayName", f"Equipment {equipment_id}"
            )
            statistic_id = self.get_statistic_id(equipment_id)
            statistic_metadata = StatisticMetaData(
                mean_type=StatisticMeanType.ARITHMETIC,
                has_sum=True,
                name=f"{self.title} {display_name}",
                source=DOMAIN,
                statistic_id=statistic_id,
                unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            )
            statistic_sum = last_sums[statistic_id]
            statistics = []
            current_hour_sum = 0.0
            current_hour_count = 0
            for energy_data in energy_data_list:
                date = energy_data.start_time.replace(
                    tzinfo=dt_util.get_default_time_zone()
                )
                value = energy_data.values.get(equipment_id, 0.0)
                current_hour_sum += value
                current_hour_count += 1
                if date.minute != 0:
                    # API returns data every 15 minutes; aggregate to 1-hour statistics
                    continue
                current_avg = current_hour_sum / current_hour_count
                statistic_sum += current_avg
                statistics.append(
                    StatisticData(start=date, state=current_avg, sum=statistic_sum)
                )
                current_hour_sum = 0.0
                current_hour_count = 0
            _LOGGER.debug(
                "Adding %s statistics for %s %s",
                len(statistics),
                statistic_id,
                display_name,
            )
            async_add_external_statistics(self.hass, statistic_metadata, statistics)

    def get_statistic_id(self, equipment_id: int) -> str:
        """Return the statistic ID for this equipment_id."""
        return f"{DOMAIN}:{self.site_id}_{equipment_id}"

    async def _async_get_last_sums(
        self, equipment_ids: Iterable[int], start_time: datetime
    ) -> dict[str, float]:
        """Get the last sum from the recorder before start_time for each statistic."""
        start = start_time - timedelta(hours=1)
        statistic_ids = {self.get_statistic_id(eq_id) for eq_id in equipment_ids}
        _LOGGER.debug(
            "Getting sum for %s statistic IDs at: %s", len(statistic_ids), start
        )
        current_stats = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period,
            self.hass,
            start,
            start + timedelta(seconds=1),
            statistic_ids,
            "hour",
            None,
            {"sum"},
        )
        result = {}
        for statistic_id in statistic_ids:
            if statistic_id in current_stats:
                statistic_sum = current_stats[statistic_id][0]["sum"]
            else:
                # If no statistics found right before start_time, try to get the last statistic
                # but use it only if it's before start_time.
                # This is needed if the integration hasn't run successfully for at least a week.
                last_stat = await get_instance(self.hass).async_add_executor_job(
                    get_last_statistics, self.hass, 1, statistic_id, True, {"sum"}
                )
                if (
                    last_stat
                    and last_stat[statistic_id][0]["start"] < start_time.timestamp()
                ):
                    statistic_sum = last_stat[statistic_id][0]["sum"]
                else:
                    # Expected for new installations or if the statistics were cleared,
                    # e.g. from the developer tools
                    statistic_sum = 0.0
            assert isinstance(statistic_sum, float)
            result[statistic_id] = statistic_sum
        return result
