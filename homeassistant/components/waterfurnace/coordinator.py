"""Data update coordinator for WaterFurnace."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import math
import random
from typing import TYPE_CHECKING

from waterfurnace.waterfurnace import (
    WaterFurnace,
    WFCredentialError,
    WFException,
    WFGateway,
    WFNoDataError,
    WFReading,
)

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.models.statistics import (
    StatisticData,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from .const import DOMAIN, ENERGY_UPDATE_INTERVAL, UPDATE_INTERVAL

if TYPE_CHECKING:
    from . import WaterFurnaceConfigEntry

_LOGGER = logging.getLogger(__name__)

BACKFILL_BATCH_DAYS = 5
BACKFILL_LOOKBACK_DAYS = 395  # 13 Months
BACKFILL_GAP_THRESHOLD = timedelta(days=BACKFILL_BATCH_DAYS)
BACKFILL_DELAY_MIN_SECONDS = 5
BACKFILL_DELAY_MAX_SECONDS = 30
BACKFILL_MAX_EMPTY_DAYS = 15


@dataclass
class WaterFurnaceDeviceData:
    """Container for per-device coordinators."""

    realtime: WaterFurnaceCoordinator
    energy: WaterFurnaceEnergyCoordinator


class WaterFurnaceCoordinator(DataUpdateCoordinator[WFReading]):
    """WaterFurnace data update coordinator.

    Polls the WaterFurnace API regularly to keep the websocket connection alive.
    The server closes the connection if no data is requested for 30 seconds,
    so frequent polling is necessary.
    """

    device_metadata: WFGateway | None

    def __init__(
        self,
        hass: HomeAssistant,
        client: WaterFurnace,
        config_entry: WaterFurnaceConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="WaterFurnace",
            update_interval=UPDATE_INTERVAL,
            config_entry=config_entry,
        )
        self.client = client
        self.unit = str(client.gwid)
        self.device_metadata = None
        if client.devices is not None:
            self.device_metadata = next(
                (device for device in client.devices if device.gwid == self.unit), None
            )

    async def _async_update_data(self):
        """Fetch data from WaterFurnace API with built-in retry logic."""
        try:
            return await self.hass.async_add_executor_job(self.client.read_with_retry)
        except WFException as err:
            raise UpdateFailed(str(err)) from err


class WaterFurnaceEnergyCoordinator(DataUpdateCoordinator[None]):
    """WaterFurnace energy data coordinator.

    Periodically fetches energy data and inserts external statistics
    for the Energy Dashboard.
    """

    config_entry: WaterFurnaceConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: WaterFurnace,
        config_entry: WaterFurnaceConfigEntry,
        gwid: str,
    ) -> None:
        """Initialize the energy coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"WaterFurnace Energy {gwid}",
            update_interval=ENERGY_UPDATE_INTERVAL,
            config_entry=config_entry,
        )
        self.client = client
        self.gwid = gwid
        self.statistic_id = f"{DOMAIN}:{gwid.lower()}_energy"
        self._backfill_task: asyncio.Task | None = None
        self._statistic_metadata = StatisticMetaData(
            has_sum=True,
            mean_type=StatisticMeanType.NONE,
            name=f"WaterFurnace Energy {gwid}",
            source=DOMAIN,
            statistic_id=self.statistic_id,
            unit_class=EnergyConverter.UNIT_CLASS,
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        )

        @callback
        def _dummy_listener() -> None:
            pass

        # Ensure periodic polling even without entity listeners,
        # since this coordinator only inserts external statistics.
        self.async_add_listener(_dummy_listener)

    async def _async_get_last_stat(self) -> tuple[float, float] | None:
        """Get the last recorded statistic timestamp and sum.

        Returns (timestamp, sum) or None if no statistics exist.
        """
        last_stat = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics, self.hass, 1, self.statistic_id, True, {"sum"}
        )
        if not last_stat:
            return None
        entry = last_stat[self.statistic_id][0]
        if "sum" not in entry or "start" not in entry or entry["sum"] is None:
            return None

        return (entry["start"], entry["sum"])

    def _fetch_energy_data(
        self, start_date: str, end_date: str
    ) -> list[tuple[datetime, float]]:
        """Fetch energy data and return list of (timestamp, kWh) tuples.

        On auth failure, re-login once and retry the request.
        """
        try:
            data = self.client.get_energy_data(
                start_date,
                end_date,
                frequency="1H",
                timezone_str=self.hass.config.time_zone,
            )
        except WFCredentialError:
            try:
                self.client.login()
            except WFCredentialError as err:
                raise UpdateFailed(
                    "Authentication failed during energy data fetch"
                ) from err
            try:
                data = self.client.get_energy_data(
                    start_date,
                    end_date,
                    frequency="1H",
                    timezone_str=self.hass.config.time_zone,
                )
            except WFCredentialError as err:
                raise UpdateFailed(
                    "Authentication failed during energy data fetch"
                ) from err
        return [
            (reading.timestamp, reading.total_power)
            for reading in data
            if reading.total_power is not None
        ]

    @staticmethod
    def _build_statistics(
        readings: list[tuple[datetime, float]],
        last_ts: float,
        last_sum: float,
        current_hour_ts: float | None = None,
    ) -> list[StatisticData]:
        """Build hourly statistics from readings, skipping already-recorded ones.

        When provided, current_hour_ts acts as an exclusive cutoff so readings at
        or after that timestamp are excluded, such as to skip the incomplete
        current hour during normal polling and backfill.
        """
        statistics: list[StatisticData] = []
        seen_hours: set[float] = set()
        running_sum = last_sum
        for timestamp, kwh in sorted(readings, key=lambda x: x[0]):
            ts = timestamp.timestamp()
            if ts <= last_ts:
                continue
            if current_hour_ts is not None and ts >= current_hour_ts:
                continue
            hour_ts = timestamp.replace(minute=0, second=0, microsecond=0).timestamp()
            if hour_ts in seen_hours:
                continue
            seen_hours.add(hour_ts)
            running_sum += kwh
            statistics.append(
                StatisticData(
                    start=timestamp.replace(minute=0, second=0, microsecond=0),
                    state=kwh,
                    sum=running_sum,
                )
            )
        return statistics

    async def _async_backfill(
        self,
        start_dt: datetime,
        end_dt: datetime,
        initial_sum: float = 0.0,
        last_ts: float = -math.inf,
    ) -> None:
        """Backfill energy statistics by walking backwards in batches.

        Collects all readings into memory, then inserts them chronologically
        in a single pass. Stops early if no data is found for
        BACKFILL_MAX_EMPTY_DAYS consecutive days.
        """
        all_readings: list[tuple[datetime, float]] = []
        batch_end = end_dt
        local_tz = dt_util.DEFAULT_TIME_ZONE
        consecutive_empty_days = 0

        while batch_end > start_dt:
            batch_start = max(batch_end - timedelta(days=BACKFILL_BATCH_DAYS), start_dt)
            start_str = batch_start.astimezone(local_tz).strftime("%Y-%m-%d")
            end_str = batch_end.astimezone(local_tz).strftime("%Y-%m-%d")

            try:
                parsed = await self.hass.async_add_executor_job(
                    self._fetch_energy_data, start_str, end_str
                )
            except WFNoDataError:
                _LOGGER.debug(
                    "No energy data for %s to %s, skipping", start_str, end_str
                )
                consecutive_empty_days += BACKFILL_BATCH_DAYS
                if consecutive_empty_days >= BACKFILL_MAX_EMPTY_DAYS:
                    _LOGGER.debug(
                        "No data for %d consecutive days, stopping backfill",
                        consecutive_empty_days,
                    )
                    break
                batch_end = batch_start
                continue
            except UpdateFailed, WFException:
                _LOGGER.exception("Error fetching energy data during backfill")
                break

            _LOGGER.debug(
                "Fetched %d readings for backfill batch %s to %s",
                len(parsed),
                start_str,
                end_str,
            )

            all_readings.extend(parsed)
            consecutive_empty_days = 0

            batch_end = batch_start
            if batch_end > start_dt:
                await asyncio.sleep(
                    random.uniform(
                        BACKFILL_DELAY_MIN_SECONDS, BACKFILL_DELAY_MAX_SECONDS
                    )
                )

        if all_readings:
            # Exclude the incomplete current hour. Use local timezone so
            # the hour boundary is correct for partial-offset timezones
            # (e.g. UTC+5:30).
            current_hour_ts = (
                end_dt.astimezone(local_tz)
                .replace(minute=0, second=0, microsecond=0)
                .timestamp()
            )
            statistics = self._build_statistics(
                all_readings, last_ts, initial_sum, current_hour_ts
            )
            if statistics:
                async_add_external_statistics(
                    self.hass, self._statistic_metadata, statistics
                )

    def _backfill_done_callback(self, task: asyncio.Task[None]) -> None:
        """Log any exception from a completed backfill task."""
        if task.cancelled():
            return
        if exc := task.exception():
            _LOGGER.error("Backfill task failed", exc_info=exc)

    async def async_wait_backfill(self) -> None:
        """Wait for any in-progress backfill task to complete."""
        if self._backfill_task:
            await self._backfill_task

    async def _async_update_data(self) -> None:
        """Fetch energy data and insert statistics.

        Handles three scenarios:
        1. No statistics exist → first-load backfill (background task)
        2. Last stat is older than gap threshold → gap backfill (background task)
        3. Last stat is recent → normal poll for recent data
        """
        if self._backfill_task and not self._backfill_task.done():
            _LOGGER.debug("Backfill already in progress, skipping update")
            return

        last = await self._async_get_last_stat()
        now = dt_util.utcnow()

        if last is None:
            # First load: backfill walking backwards from today
            start = now - timedelta(days=BACKFILL_LOOKBACK_DAYS)
            self._backfill_task = self.config_entry.async_create_background_task(
                self.hass,
                self._async_backfill(start, now),
                f"waterfurnace_backfill_{self.gwid}",
            )
            self._backfill_task.add_done_callback(self._backfill_done_callback)
            return

        last_ts, last_sum = last
        last_dt = dt_util.utc_from_timestamp(last_ts)

        if now - last_dt > BACKFILL_GAP_THRESHOLD:
            # Large gap detected, backfill using batches
            self._backfill_task = self.config_entry.async_create_background_task(
                self.hass,
                self._async_backfill(last_dt, now, last_sum, last_ts),
                f"waterfurnace_backfill_{self.gwid}",
            )
            self._backfill_task.add_done_callback(self._backfill_done_callback)
            return

        # Normal poll: fetch recent data (up to BACKFILL_GAP_THRESHOLD) and insert any missing hours
        _LOGGER.debug("Last stat: ts=%s, sum=%s", last_dt.isoformat(), last_sum)
        local_tz = dt_util.DEFAULT_TIME_ZONE
        start_date = last_dt.astimezone(local_tz).strftime("%Y-%m-%d")
        end_date = (now.astimezone(local_tz) + timedelta(days=1)).strftime("%Y-%m-%d")

        try:
            readings = await self.hass.async_add_executor_job(
                self._fetch_energy_data, start_date, end_date
            )
        except WFNoDataError:
            _LOGGER.debug("No energy data available for %s to %s", start_date, end_date)
            return
        except WFException as err:
            raise UpdateFailed(str(err)) from err

        if not readings:
            _LOGGER.debug("No readings returned for %s to %s", start_date, end_date)
            return

        _LOGGER.debug("Fetched %s readings", len(readings))

        # Use local timezone so the hour boundary is correct for
        # partial-offset timezones (e.g. UTC+5:30).
        current_hour_ts = (
            now.astimezone(local_tz)
            .replace(minute=0, second=0, microsecond=0)
            .timestamp()
        )
        statistics = self._build_statistics(
            readings, last_ts, last_sum, current_hour_ts
        )

        _LOGGER.debug("Built %s statistics to insert", len(statistics))

        if statistics:
            async_add_external_statistics(
                self.hass, self._statistic_metadata, statistics
            )
