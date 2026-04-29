"""Coordinator for Tibber sensors."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
import random
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
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
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


class TibberCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Base Tibber coordinator."""

    config_entry: TibberConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TibberConfigEntry,
        *,
        name: str,
        update_interval: timedelta | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=name,
            update_interval=update_interval,
        )
        self._runtime_data = config_entry.runtime_data

    async def _async_get_client(self) -> tibber.Tibber:
        """Get the Tibber client with error handling."""
        try:
            return await self._runtime_data.async_get_client(self.hass)
        except (ClientError, TimeoutError, tibber.exceptions.HttpExceptionError) as err:
            raise UpdateFailed(f"Unable to create Tibber client: {err}") from err


class TibberDataCoordinator(TibberCoordinator[None]):
    """Handle Tibber data and insert statistics."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TibberConfigEntry,
        tibber_connection: tibber.Tibber,
    ) -> None:
        """Initialize the data handler."""
        super().__init__(
            hass,
            config_entry,
            name=f"Tibber {tibber_connection.name}",
            update_interval=timedelta(minutes=20),
        )

    async def _async_update_data(self) -> None:
        """Update data via API."""
        tibber_connection = await self._async_get_client()

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
        tibber_connection = await self._async_get_client()
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


class TibberPriceCoordinator(TibberCoordinator[dict[str, TibberHomeData]]):
    """Handle Tibber price data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TibberConfigEntry,
        price_fetch_coordinator: TibberFetchPriceCoordinator,
    ) -> None:
        """Initialize the price coordinator."""
        super().__init__(
            hass,
            config_entry,
            name=f"{DOMAIN} price",
        )
        self._price_fetch_coordinator = price_fetch_coordinator
        self._unsub_price_fetch_listener: CALLBACK_TYPE | None = None

    @callback
    def _build_price_data(self) -> dict[str, TibberHomeData]:
        """Build derived price data from the fetched Tibber homes."""
        return {
            home_id: _build_home_data(home)
            for home_id, home in (self._price_fetch_coordinator.data or {}).items()
        }

    @callback
    def _async_handle_price_fetch_update(self) -> None:
        """Update derived price data when fetched prices change."""
        self.update_interval = self._time_until_next_15_minute()
        self.async_set_updated_data(self._build_price_data())

    @callback
    def _schedule_refresh(self) -> None:
        """Start listening to fetched price data when entities subscribe."""
        super()._schedule_refresh()
        if self._unsub_price_fetch_listener is None:
            self._unsub_price_fetch_listener = (
                self._price_fetch_coordinator.async_add_listener(
                    self._async_handle_price_fetch_update
                )
            )

    def _unschedule_refresh(self) -> None:
        """Stop listening to fetched price data when unused."""
        super()._unschedule_refresh()
        if self._unsub_price_fetch_listener is not None:
            self._unsub_price_fetch_listener()
            self._unsub_price_fetch_listener = None

    def _time_until_next_15_minute(self) -> timedelta:
        """Return time until the next 15-minute boundary (0, 15, 30, 45) in UTC."""
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
        return next_run - now

    async def _async_update_data(self) -> dict[str, TibberHomeData]:
        self.update_interval = self._time_until_next_15_minute()
        return self._build_price_data()


class TibberFetchPriceCoordinator(TibberCoordinator[dict[str, tibber.TibberHome]]):
    """Fetch Tibber price data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TibberConfigEntry,
    ) -> None:
        """Initialize the price coordinator."""
        super().__init__(
            hass,
            config_entry,
            name=f"{DOMAIN} price fetch",
        )
        self._tomorrow_price_poll_threshold_seconds = random.uniform(
            3600 * 14, 3600 * 22
        )

    async def _async_update_data(self) -> dict[str, tibber.TibberHome]:
        """Fetch latest price data via API and return per-home data."""
        tibber_connection = await self._async_get_client()
        active_homes = tibber_connection.get_homes(only_active=True)

        now = dt_util.now()
        today_start = dt_util.start_of_local_day(now)
        today_end = today_start + timedelta(days=1)
        tomorrow_start = today_end
        tomorrow_end = tomorrow_start + timedelta(days=1)

        def _has_prices_today(home: tibber.TibberHome) -> bool:
            """Return True if the home has any prices today."""
            for start in home.price_total:
                start_dt = dt_util.as_local(datetime.fromisoformat(str(start)))
                if today_start <= start_dt < today_end:
                    return True
            return False

        def _has_prices_tomorrow(home: tibber.TibberHome) -> bool:
            """Return True if the home has any prices tomorrow."""
            for start in home.price_total:
                start_dt = dt_util.as_local(datetime.fromisoformat(str(start)))
                if tomorrow_start <= start_dt < tomorrow_end:
                    return True
            return False

        def _needs_update(home: tibber.TibberHome) -> bool:
            """Return True if the home needs to be updated."""
            if not _has_prices_today(home):
                return True
            if _has_prices_tomorrow(home):
                return False
            if now >= today_start + timedelta(
                seconds=self._tomorrow_price_poll_threshold_seconds
            ):
                return True
            return False

        self.update_interval = timedelta(seconds=random.uniform(60, 60 * 10))

        try:
            await asyncio.gather(
                *(
                    home.update_info_and_price_info()
                    for home in active_homes
                    if _needs_update(home)
                )
            )
        except tibber.exceptions.RateLimitExceededError as err:
            raise UpdateFailed(
                f"Rate limit exceeded, retry after {err.retry_after} seconds",
                retry_after=err.retry_after,
            ) from err
        except tibber.exceptions.HttpExceptionError as err:
            raise UpdateFailed(f"Error communicating with API ({err})") from err

        return {home.home_id: home for home in active_homes}


class TibberDataAPICoordinator(TibberCoordinator[dict[str, TibberDevice]]):
    """Fetch and cache Tibber Data API device capabilities."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TibberConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            entry,
            name=f"{DOMAIN} Data API",
            update_interval=timedelta(minutes=1),
        )
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
