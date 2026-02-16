"""Coordinator for Tibber sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any, cast

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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, UnitOfEnergy
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from .const import DOMAIN

if TYPE_CHECKING:
    from tibber import TibberHome

    from .const import TibberConfigEntry

FIVE_YEARS = 5 * 365 * 24

_LOGGER = logging.getLogger(__name__)


@dataclass
class TibberHomeData:
    """Structured data per Tibber home from GraphQL and price API."""

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

    def __getitem__(self, key: str) -> Any:
        """Return attribute by name, or None if missing."""
        return self.__dict__.get(key)


def _build_home_data(home: TibberHome) -> TibberHomeData:
    """Build TibberHomeData from a TibberHome after price info has been fetched."""
    price_value, price_time, price_rank = home.current_price_data()
    attrs = home.current_attributes()
    return TibberHomeData(
        currency=home.currency,
        price_unit=home.price_unit,
        current_price=price_value,
        current_price_time=price_time,
        intraday_price_ranking=price_rank,
        max_price=attrs.get("max_price", 0.0),
        avg_price=attrs.get("avg_price", 0.0),
        min_price=attrs.get("min_price", 0.0),
        off_peak_1=attrs.get("off_peak_1", 0.0),
        peak=attrs.get("peak", 0.0),
        off_peak_2=attrs.get("off_peak_2", 0.0),
        month_cost=getattr(home, "month_cost", None),
        peak_hour=getattr(home, "peak_hour", None),
        peak_hour_time=getattr(home, "peak_hour_time", None),
        month_cons=getattr(home, "month_cons", None),
    )


class TibberDataCoordinator(DataUpdateCoordinator[dict[str, TibberHomeData]]):
    """Handle Tibber data and insert statistics."""

    config_entry: TibberConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TibberConfigEntry,
    ) -> None:
        """Initialize the data handler."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Tibber",
        )
        self._listener_unsub: Callable[[], None] | None = None

    def _get_next_15_interval(self) -> datetime:
        """Return the next 15-minute boundary (minutes 0, 15, 30, 45) in UTC."""
        next_run = dt_util.utcnow() + timedelta(minutes=15)
        next_minute = (next_run.minute // 15) * 15
        return next_run.replace(
            minute=next_minute, second=0, microsecond=0, tzinfo=dt_util.UTC
        )

    @callback
    def _on_scheduled_refresh(self, _fire_time: datetime) -> None:
        """Run the scheduled refresh (same contract as base refresh interval)."""
        self.config_entry.async_create_background_task(
            self.hass,
            self._handle_refresh_interval(),
            name=f"{self.name} - {self.config_entry.title} - refresh",
            eager_start=True,
        )

    @callback
    def _schedule_refresh(self) -> None:
        """Schedule a refresh at the next 15-minute boundary."""
        if self.config_entry.pref_disable_polling:
            return
        self._async_unsub_refresh()
        self._unsub_refresh = async_track_point_in_utc_time(
            self.hass,
            self._on_scheduled_refresh,
            self._get_next_15_interval(),
        )

    async def _async_update_data(self) -> dict[str, TibberHomeData]:
        """Update data via API and return per-home data for sensors."""
        _LOGGER.error("Updating data")
        tibber_connection = await self.config_entry.runtime_data.async_get_client(
            self.hass
        )
        try:
            await tibber_connection.fetch_consumption_data_active_homes()
            await tibber_connection.fetch_production_data_active_homes()
            now = dt_util.now()
            for home in tibber_connection.get_homes(only_active=True):
                update_needed = False
                last_data_timestamp = home.last_data_timestamp

                if last_data_timestamp is None:
                    update_needed = True
                else:
                    remaining_seconds = (last_data_timestamp - now).total_seconds()
                    if remaining_seconds < 11 * 3600:
                        update_needed = True

                if update_needed:
                    await home.update_info_and_price_info()
            await self._insert_statistics(tibber_connection)
        except tibber.RetryableHttpExceptionError as err:
            raise UpdateFailed(f"Error communicating with API ({err.status})") from err
        except tibber.FatalHttpExceptionError as err:
            raise UpdateFailed(f"Error communicating with API ({err.status})") from err

        result: dict[str, TibberHomeData] = {}
        for home in tibber_connection.get_homes(only_active=True):
            result[home.home_id] = _build_home_data(home)
        return result

    async def _insert_statistics(self, tibber_connection: tibber.Tibber) -> None:
        """Insert Tibber statistics."""
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
            return await self.config_entry.runtime_data.async_get_client(self.hass)
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


class TibberRtDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Handle Tibber realtime data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        add_sensor_callback: Callable[[TibberRtDataCoordinator, Any], None],
        tibber_home: TibberHome,
    ) -> None:
        """Initialize the data handler."""
        self._add_sensor_callback = add_sensor_callback
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=tibber_home.info["viewer"]["home"]["address"].get(
                "address1", "Tibber"
            ),
        )

        self._async_remove_device_updates_handler = self.async_add_listener(
            self._data_updated
        )
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._handle_ha_stop)

    @callback
    def _handle_ha_stop(self, _event: Event) -> None:
        """Handle Home Assistant stopping."""
        self._async_remove_device_updates_handler()

    @callback
    def _data_updated(self) -> None:
        """Triggered when data is updated."""
        if live_measurement := self.get_live_measurement():
            self._add_sensor_callback(self, live_measurement)

    def get_live_measurement(self) -> Any:
        """Get live measurement data."""
        if errors := self.data.get("errors"):
            _LOGGER.error(errors[0])
            return None
        return self.data.get("data", {}).get("liveMeasurement")
