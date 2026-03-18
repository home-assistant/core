"""Coordinator for Tibber sensors."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, TypedDict, cast

from aiohttp.client_exceptions import ClientError
import tibber
from tibber.data_api import TibberDevice

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
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from .const import DOMAIN

if TYPE_CHECKING:
    from .const import TibberConfigEntry

FIVE_YEARS = 5 * 365 * 24

_LOGGER = logging.getLogger(__name__)


class TibberHomeData(TypedDict):
    """Data for a Tibber home used by the price sensor."""

    currency: str
    price_unit: str
    current_price: float | None
    current_price_time: datetime | None
    intraday_price_ranking: float | None
    max_price: float
    avg_price: float
    min_price: float
    off_peak_1: float
    peak: float
    off_peak_2: float
    month_cost: float | None
    peak_hour: float | None
    peak_hour_time: datetime | None
    month_cons: float | None
    app_nickname: str | None
    grid_company: str | None
    estimated_annual_consumption: int | None


def _build_home_data(home: tibber.TibberHome) -> TibberHomeData:
    """Build TibberHomeData from a TibberHome for the price sensor."""
    current_price, last_updated, price_rank = home.current_price_data()
    attributes = home.current_attributes()
    result: TibberHomeData = {
        "currency": home.currency,
        "price_unit": home.price_unit,
        "current_price": current_price,
        "current_price_time": last_updated,
        "intraday_price_ranking": price_rank,
        "max_price": attributes["max_price"],
        "avg_price": attributes["avg_price"],
        "min_price": attributes["min_price"],
        "off_peak_1": attributes["off_peak_1"],
        "peak": attributes["peak"],
        "off_peak_2": attributes["off_peak_2"],
        "month_cost": home.month_cost,
        "peak_hour": home.peak_hour,
        "peak_hour_time": home.peak_hour_time,
        "month_cons": home.month_cons,
        "app_nickname": home.info["viewer"]["home"].get("appNickname"),
        "grid_company": home.info["viewer"]["home"]["meteringPointData"]["gridCompany"],
        "estimated_annual_consumption": home.info["viewer"]["home"][
            "meteringPointData"
        ]["estimatedAnnualConsumption"],
    }
    return result


class TibberDataCoordinator(DataUpdateCoordinator[None]):
    """Handle Tibber data and insert statistics."""

    config_entry: TibberConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TibberConfigEntry,
        tibber_connection: tibber.Tibber,
    ) -> None:
        """Initialize the data handler."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"Tibber {tibber_connection.name}",
            update_interval=timedelta(minutes=20),
        )

    async def _async_update_data(self) -> None:
        """Update data via API."""
        tibber_connection = await self.config_entry.runtime_data.async_get_client(
            self.hass
        )

        try:
            await tibber_connection.fetch_consumption_data_active_homes()
            await tibber_connection.fetch_production_data_active_homes()
            await self._insert_statistics()
        except tibber.RetryableHttpExceptionError as err:
            raise UpdateFailed(f"Error communicating with API ({err.status})") from err
        except tibber.FatalHttpExceptionError:
            # Fatal error. Reload config entry to show correct error.
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.config_entry.entry_id)
            )

    async def _insert_statistics(self) -> None:
        """Insert Tibber statistics."""
        tibber_connection = await self.config_entry.runtime_data.async_get_client(
            self.hass
        )
        for home in tibber_connection.get_homes():
            sensors: list[tuple[str, bool, str | None, str]] = []
            if home.hourly_consumption_data:
                sensors.append(
                    (
                        "consumption",
                        False,
                        EnergyConverter.UNIT_CLASS,
                        UnitOfEnergy.KILO_WATT_HOUR,
                    )
                )
                sensors.append(("totalCost", False, None, home.currency))
            if home.hourly_production_data:
                sensors.append(
                    (
                        "production",
                        True,
                        EnergyConverter.UNIT_CLASS,
                        UnitOfEnergy.KILO_WATT_HOUR,
                    )
                )
                sensors.append(("profit", True, None, home.currency))

            for sensor_type, is_production, unit_class, unit in sensors:
                statistic_id = (
                    f"{DOMAIN}:energy_"
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
                    mean_type=StatisticMeanType.NONE,
                    has_sum=True,
                    name=f"{home.name} {sensor_type}",
                    source=DOMAIN,
                    statistic_id=statistic_id,
                    unit_class=unit_class,
                    unit_of_measurement=unit,
                )
                async_add_external_statistics(self.hass, metadata, statistics)


class TibberPriceCoordinator(DataUpdateCoordinator[dict[str, TibberHomeData]]):
    """Handle Tibber price data and insert statistics."""

    config_entry: TibberConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TibberConfigEntry,
    ) -> None:
        """Initialize the price coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} price",
            update_interval=timedelta(minutes=1),
        )

    def _seconds_until_next_15_minute(self) -> float:
        """Return seconds until the next 15-minute boundary (0, 15, 30, 45) in UTC."""
        now = dt_util.utcnow()
        next_minute = ((now.minute // 15) + 1) * 15
        if next_minute >= 60:
            next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(
                hours=1
            )
        else:
            next_run = now.replace(
                minute=next_minute, second=0, microsecond=0, tzinfo=dt_util.UTC
            )
        return (next_run - now).total_seconds()

    async def _async_update_data(self) -> dict[str, TibberHomeData]:
        """Update data via API and return per-home data for sensors."""
        tibber_connection = await self.config_entry.runtime_data.async_get_client(
            self.hass
        )
        active_homes = tibber_connection.get_homes(only_active=True)
        try:
            await asyncio.gather(
                tibber_connection.fetch_consumption_data_active_homes(),
                tibber_connection.fetch_production_data_active_homes(),
            )

            now = dt_util.now()
            homes_to_update = [
                home
                for home in active_homes
                if (
                    (last_data_timestamp := home.last_data_timestamp) is None
                    or (last_data_timestamp - now).total_seconds() < 11 * 3600
                )
            ]

            if homes_to_update:
                await asyncio.gather(
                    *(home.update_info_and_price_info() for home in homes_to_update)
                )
        except tibber.RetryableHttpExceptionError as err:
            raise UpdateFailed(f"Error communicating with API ({err.status})") from err
        except tibber.FatalHttpExceptionError as err:
            raise UpdateFailed(f"Error communicating with API ({err.status})") from err

        result = {home.home_id: _build_home_data(home) for home in active_homes}

        self.update_interval = timedelta(seconds=self._seconds_until_next_15_minute())
        return result


class TibberDataAPICoordinator(DataUpdateCoordinator[dict[str, TibberDevice]]):
    """Fetch and cache Tibber Data API device capabilities."""

    config_entry: TibberConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TibberConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} Data API",
            update_interval=timedelta(minutes=1),
            config_entry=entry,
        )
        self._runtime_data = entry.runtime_data
        self.sensors_by_device: dict[str, dict[str, tibber.data_api.Sensor]] = {}

    def _build_sensor_lookup(self, devices: dict[str, TibberDevice]) -> None:
        """Build sensor lookup dict for efficient access."""
        self.sensors_by_device = {
            device_id: {sensor.id: sensor for sensor in device.sensors}
            for device_id, device in devices.items()
        }

    def get_sensor(
        self, device_id: str, sensor_id: str
    ) -> tibber.data_api.Sensor | None:
        """Get a sensor by device and sensor ID."""
        if device_sensors := self.sensors_by_device.get(device_id):
            return device_sensors.get(sensor_id)
        return None

    async def _async_get_client(self) -> tibber.Tibber:
        """Get the Tibber client with error handling."""
        try:
            return await self._runtime_data.async_get_client(self.hass)
        except ConfigEntryAuthFailed:
            raise
        except (ClientError, TimeoutError, tibber.UserAgentMissingError) as err:
            raise UpdateFailed(f"Unable to create Tibber client: {err}") from err

    async def _async_setup(self) -> None:
        """Initial load of Tibber Data API devices."""
        client = await self._async_get_client()
        devices = await client.data_api.get_all_devices()
        self._build_sensor_lookup(devices)

    async def _async_update_data(self) -> dict[str, TibberDevice]:
        """Fetch the latest device capabilities from the Tibber Data API."""
        client = await self._async_get_client()
        try:
            devices: dict[str, TibberDevice] = await client.data_api.update_devices()
        except tibber.exceptions.RateLimitExceededError as err:
            raise UpdateFailed(
                f"Rate limit exceeded, retry after {err.retry_after} seconds",
                retry_after=err.retry_after,
            ) from err
        self._build_sensor_lookup(devices)
        return devices
