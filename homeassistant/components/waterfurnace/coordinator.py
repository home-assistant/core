"""Data update coordinator for WaterFurnace."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
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
        if entry["sum"] is None:
            return None
        return (entry["start"], entry["sum"])

    def _fetch_energy_data(
        self, start_date: str, end_date: str
    ) -> list[tuple[datetime, float]]:
        """Fetch energy data and return list of (timestamp, kWh) tuples."""
        # Re-login to refresh the HTTP session token, which expires between
        # the 2-hour polling intervals.
        try:
            self.client.login()
        except WFCredentialError as err:
            raise UpdateFailed(
                "Authentication failed during energy data fetch"
            ) from err
        data = self.client.get_energy_data(
            start_date,
            end_date,
            frequency="1H",
            timezone_str=self.hass.config.time_zone,
        )
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
        now: datetime,
    ) -> list[StatisticData]:
        """Build hourly statistics from readings, skipping already-recorded ones."""
        current_hour_ts = now.replace(minute=0, second=0, microsecond=0).timestamp()
        statistics: list[StatisticData] = []
        seen_hours: set[float] = set()
        running_sum = last_sum
        for timestamp, kwh in sorted(readings, key=lambda x: x[0]):
            ts = timestamp.timestamp()
            if ts <= last_ts:
                continue
            if ts >= current_hour_ts:
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

    async def _async_update_data(self) -> None:
        """Fetch energy data and insert statistics."""
        last = await self._async_get_last_stat()
        now = dt_util.utcnow()

        if last is None:
            _LOGGER.info("No prior statistics found, fetching recent energy data")
            last_ts = 0.0
            last_sum = 0.0
            start_dt = now - timedelta(days=1)
        else:
            last_ts, last_sum = last
            start_dt = dt_util.utc_from_timestamp(last_ts)
            _LOGGER.debug("Last stat: ts=%s, sum=%s", start_dt.isoformat(), last_sum)

        local_tz = dt_util.DEFAULT_TIME_ZONE
        start_date = start_dt.astimezone(local_tz).strftime("%Y-%m-%d")
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

        statistics = self._build_statistics(readings, last_ts, last_sum, now)

        _LOGGER.debug("Built %s statistics to insert", len(statistics))

        if statistics:
            async_add_external_statistics(
                self.hass, self._statistic_metadata, statistics
            )
