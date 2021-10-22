"""The National Weather Service integration."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
import datetime
import logging

from pynws import SimpleNWS

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import debounce
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import utcnow

from .const import (
    CONF_STATION,
    COORDINATOR_FORECAST,
    COORDINATOR_FORECAST_HOURLY,
    COORDINATOR_OBSERVATION,
    DOMAIN,
    NWS_DATA,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "weather"]

DEFAULT_SCAN_INTERVAL = datetime.timedelta(minutes=10)
FAILED_SCAN_INTERVAL = datetime.timedelta(minutes=1)
DEBOUNCE_TIME = 60  # in seconds


def base_unique_id(latitude, longitude):
    """Return unique id for entries in configuration."""
    return f"{latitude}_{longitude}"


class NwsDataUpdateCoordinator(DataUpdateCoordinator):
    """
    NWS data update coordinator.

    Implements faster data update intervals for failed updates and exposes a last successful update time.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        *,
        name: str,
        update_interval: datetime.timedelta,
        failed_update_interval: datetime.timedelta,
        update_method: Callable[[], Awaitable] | None = None,
        request_refresh_debouncer: debounce.Debouncer | None = None,
    ) -> None:
        """Initialize NWS coordinator."""
        super().__init__(
            hass,
            logger,
            name=name,
            update_interval=update_interval,
            update_method=update_method,
            request_refresh_debouncer=request_refresh_debouncer,
        )
        self.failed_update_interval = failed_update_interval
        self.last_update_success_time = None

    @callback
    def _schedule_refresh(self) -> None:
        """Schedule a refresh."""
        if self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None

        # We _floor_ utcnow to create a schedule on a rounded second,
        # minimizing the time between the point and the real activation.
        # That way we obtain a constant update frequency,
        # as long as the update process takes less than a second
        if self.last_update_success:
            update_interval = self.update_interval
            self.last_update_success_time = utcnow()
        else:
            update_interval = self.failed_update_interval
        self._unsub_refresh = async_track_point_in_utc_time(
            self.hass,
            self._handle_refresh_interval,
            utcnow().replace(microsecond=0) + update_interval,
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a National Weather Service entry."""
    latitude = entry.data[CONF_LATITUDE]
    longitude = entry.data[CONF_LONGITUDE]
    api_key = entry.data[CONF_API_KEY]
    station = entry.data[CONF_STATION]

    client_session = async_get_clientsession(hass)

    # set_station only does IO when station is None
    nws_data = SimpleNWS(latitude, longitude, api_key, client_session)
    await nws_data.set_station(station)

    coordinator_observation = NwsDataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"NWS observation station {station}",
        update_method=nws_data.update_observation,
        update_interval=DEFAULT_SCAN_INTERVAL,
        failed_update_interval=FAILED_SCAN_INTERVAL,
        request_refresh_debouncer=debounce.Debouncer(
            hass, _LOGGER, cooldown=DEBOUNCE_TIME, immediate=True
        ),
    )

    coordinator_forecast = NwsDataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"NWS forecast station {station}",
        update_method=nws_data.update_forecast,
        update_interval=DEFAULT_SCAN_INTERVAL,
        failed_update_interval=FAILED_SCAN_INTERVAL,
        request_refresh_debouncer=debounce.Debouncer(
            hass, _LOGGER, cooldown=DEBOUNCE_TIME, immediate=True
        ),
    )

    coordinator_forecast_hourly = NwsDataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"NWS forecast hourly station {station}",
        update_method=nws_data.update_forecast_hourly,
        update_interval=DEFAULT_SCAN_INTERVAL,
        failed_update_interval=FAILED_SCAN_INTERVAL,
        request_refresh_debouncer=debounce.Debouncer(
            hass, _LOGGER, cooldown=DEBOUNCE_TIME, immediate=True
        ),
    )
    nws_hass_data = hass.data.setdefault(DOMAIN, {})
    nws_hass_data[entry.entry_id] = {
        NWS_DATA: nws_data,
        COORDINATOR_OBSERVATION: coordinator_observation,
        COORDINATOR_FORECAST: coordinator_forecast,
        COORDINATOR_FORECAST_HOURLY: coordinator_forecast_hourly,
    }

    # Fetch initial data so we have data when entities subscribe
    await coordinator_observation.async_refresh()
    await coordinator_forecast.async_refresh()
    await coordinator_forecast_hourly.async_refresh()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if len(hass.data[DOMAIN]) == 0:
            hass.data.pop(DOMAIN)
    return unload_ok
