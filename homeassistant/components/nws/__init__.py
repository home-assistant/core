"""The National Weather Service integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import datetime
from functools import partial
import logging

from pynws import SimpleNWS, call_with_retry

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import debounce
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import TimestampDataUpdateCoordinator
from homeassistant.util.dt import utcnow

from .const import CONF_STATION, DOMAIN, UPDATE_TIME_PERIOD

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.WEATHER]

DEFAULT_SCAN_INTERVAL = datetime.timedelta(minutes=10)
RETRY_INTERVAL = datetime.timedelta(minutes=1)
RETRY_STOP = datetime.timedelta(minutes=10)

DEBOUNCE_TIME = 10 * 60  # in seconds

type NWSConfigEntry = ConfigEntry[NWSData]


def base_unique_id(latitude: float, longitude: float) -> str:
    """Return unique id for entries in configuration."""
    return f"{latitude}_{longitude}"


@dataclass
class NWSData:
    """Data for the National Weather Service integration."""

    api: SimpleNWS
    coordinator_observation: TimestampDataUpdateCoordinator[None]
    coordinator_forecast: TimestampDataUpdateCoordinator[None]
    coordinator_forecast_hourly: TimestampDataUpdateCoordinator[None]


async def async_setup_entry(hass: HomeAssistant, entry: NWSConfigEntry) -> bool:
    """Set up a National Weather Service entry."""
    latitude = entry.data[CONF_LATITUDE]
    longitude = entry.data[CONF_LONGITUDE]
    api_key = entry.data[CONF_API_KEY]
    station = entry.data[CONF_STATION]

    client_session = async_get_clientsession(hass)

    # set_station only does IO when station is None
    nws_data = SimpleNWS(latitude, longitude, api_key, client_session)
    await nws_data.set_station(station)

    def async_setup_update_observation(
        retry_interval: datetime.timedelta | float,
        retry_stop: datetime.timedelta | float,
    ) -> Callable[[], Awaitable[None]]:
        async def update_observation() -> None:
            """Retrieve recent observations."""
            await call_with_retry(
                nws_data.update_observation,
                retry_interval,
                retry_stop,
                start_time=utcnow() - UPDATE_TIME_PERIOD,
            )

        return update_observation

    def async_setup_update_forecast(
        retry_interval: datetime.timedelta | float,
        retry_stop: datetime.timedelta | float,
    ) -> Callable[[], Awaitable[None]]:
        return partial(
            call_with_retry,
            nws_data.update_forecast,
            retry_interval,
            retry_stop,
        )

    def async_setup_update_forecast_hourly(
        retry_interval: datetime.timedelta | float,
        retry_stop: datetime.timedelta | float,
    ) -> Callable[[], Awaitable[None]]:
        return partial(
            call_with_retry,
            nws_data.update_forecast_hourly,
            retry_interval,
            retry_stop,
        )

    # Don't use retries in setup
    coordinator_observation = TimestampDataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"NWS observation station {station}",
        update_method=async_setup_update_observation(0, 0),
        update_interval=DEFAULT_SCAN_INTERVAL,
        request_refresh_debouncer=debounce.Debouncer(
            hass, _LOGGER, cooldown=DEBOUNCE_TIME, immediate=True
        ),
    )

    coordinator_forecast = TimestampDataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"NWS forecast station {station}",
        update_method=async_setup_update_forecast(0, 0),
        update_interval=DEFAULT_SCAN_INTERVAL,
        request_refresh_debouncer=debounce.Debouncer(
            hass, _LOGGER, cooldown=DEBOUNCE_TIME, immediate=True
        ),
    )

    coordinator_forecast_hourly = TimestampDataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"NWS forecast hourly station {station}",
        update_method=async_setup_update_forecast_hourly(0, 0),
        update_interval=DEFAULT_SCAN_INTERVAL,
        request_refresh_debouncer=debounce.Debouncer(
            hass, _LOGGER, cooldown=DEBOUNCE_TIME, immediate=True
        ),
    )
    entry.runtime_data = NWSData(
        nws_data,
        coordinator_observation,
        coordinator_forecast,
        coordinator_forecast_hourly,
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator_observation.async_refresh()
    await coordinator_forecast.async_refresh()
    await coordinator_forecast_hourly.async_refresh()

    # Use retries
    coordinator_observation.update_method = async_setup_update_observation(
        RETRY_INTERVAL, RETRY_STOP
    )
    coordinator_forecast.update_method = async_setup_update_forecast(
        RETRY_INTERVAL, RETRY_STOP
    )
    coordinator_forecast_hourly.update_method = async_setup_update_forecast_hourly(
        RETRY_INTERVAL, RETRY_STOP
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NWSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def device_info(latitude: float, longitude: float) -> DeviceInfo:
    """Return device registry information."""
    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, base_unique_id(latitude, longitude))},
        manufacturer="National Weather Service",
        name=f"NWS: {latitude}, {longitude}",
    )
