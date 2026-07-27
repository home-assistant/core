"""The NWS coordinator."""

from datetime import datetime
import logging
from typing import TYPE_CHECKING, override

import aiohttp
from aiohttp import ClientResponseError
from pynws import NwsError, NwsNoDataError, SimpleNWS, call_with_retry

from homeassistant.const import CONF_API_KEY, EntityStateAttribute
from homeassistant.core import HomeAssistant
from homeassistant.helpers import debounce
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.location import has_location
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import location as location_util
from homeassistant.util.dt import utcnow

if TYPE_CHECKING:
    from . import NWSConfigEntry

from .const import (
    CONF_STATION,
    DEBOUNCE_TIME,
    DEFAULT_SCAN_INTERVAL,
    LOCATION_CHANGE_THRESHOLD,
    OBSERVATION_VALID_TIME,
    RETRY_INTERVAL,
    RETRY_STOP,
    UPDATE_TIME_PERIOD,
)

_LOGGER = logging.getLogger(__name__)


class NWSObservationDataUpdateCoordinator(TimestampDataUpdateCoordinator[None]):
    """Class to manage fetching NWS observation data."""

    config_entry: NWSConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: NWSConfigEntry,
        nws: SimpleNWS,
        *,
        location_entity_id: str | None = None,
        initial_position: tuple[float, float] | None = None,
    ) -> None:
        """Initialize."""
        self.nws = nws
        self.last_api_success_time: datetime | None = None
        self.initialized: bool = False
        self._location_entity_id = location_entity_id
        self._previous_position = initial_position
        self._location_state_warned = False

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"NWS observation station {nws.station}",
            update_interval=DEFAULT_SCAN_INTERVAL,
            request_refresh_debouncer=debounce.Debouncer(
                hass, _LOGGER, cooldown=DEBOUNCE_TIME, immediate=True
            ),
        )

    async def _async_check_location_change(self) -> None:
        """Check if the tracked location entity has moved and update the API."""
        assert self._location_entity_id is not None
        state = self.hass.states.get(self._location_entity_id)
        if state is None:
            if not self._location_state_warned:
                _LOGGER.warning(
                    "Location entity %s is unavailable; skipping location update",
                    self._location_entity_id,
                )
                self._location_state_warned = True
            return
        self._location_state_warned = False

        if not has_location(state):
            _LOGGER.debug(
                "Location entity %s has no location attributes; skipping location update",
                self._location_entity_id,
            )
            return
        new_lat = state.attributes[EntityStateAttribute.LATITUDE]
        new_lon = state.attributes[EntityStateAttribute.LONGITUDE]
        if self._previous_position is not None:
            prev_lat, prev_lon = self._previous_position
            if new_lat == prev_lat and new_lon == prev_lon:
                return
            dist = location_util.distance(prev_lat, prev_lon, new_lat, new_lon)
            if dist is not None and dist <= LOCATION_CHANGE_THRESHOLD:
                return
        client_session = async_get_clientsession(self.hass)
        api_key = self.config_entry.data[CONF_API_KEY]
        station = self.config_entry.data.get(CONF_STATION)
        try:
            new_nws = SimpleNWS(new_lat, new_lon, api_key, client_session)
            await new_nws.set_station(station)
        except aiohttp.ClientError, NwsError:
            _LOGGER.exception(
                "Failed to update location for %s, continuing with previous station",
                self._location_entity_id,
            )
            return
        _LOGGER.info(
            "NWS API updated: station %s at (%.4f, %.4f)",
            new_nws.station,
            new_lat,
            new_lon,
        )
        self.nws = new_nws
        self.name = f"NWS observation station {new_nws.station}"
        runtime_data = self.config_entry.runtime_data
        runtime_data.api = new_nws
        runtime_data.latitude = new_lat
        runtime_data.longitude = new_lon
        self._previous_position = (new_lat, new_lon)
        self.initialized = False
        self.last_api_success_time = None
        runtime_data.coordinator_forecast.name = (
            f"NWS forecast station {new_nws.station}"
        )
        runtime_data.coordinator_forecast_hourly.name = (
            f"NWS forecast hourly station {new_nws.station}"
        )
        await runtime_data.coordinator_forecast.async_refresh()
        await runtime_data.coordinator_forecast_hourly.async_refresh()

    @override
    async def _async_update_data(self) -> None:
        """Update data via library."""
        if self._location_entity_id:
            await self._async_check_location_change()
        if not self.initialized:
            await self._async_first_update_data()
        else:
            await self._async_subsequent_update_data()

    async def _async_first_update_data(self):
        """Update data without retries first."""
        try:
            await self.nws.update_observation(
                raise_no_data=True,
                start_time=utcnow() - UPDATE_TIME_PERIOD,
            )
        except (NwsNoDataError, ClientResponseError) as err:
            raise UpdateFailed(err) from err
        else:
            self.last_api_success_time = utcnow()
        finally:
            self.initialized = True

    async def _async_subsequent_update_data(self) -> None:
        """Update data with retries and caching data over multiple failed rounds."""
        try:
            await call_with_retry(
                self.nws.update_observation,
                RETRY_INTERVAL,
                RETRY_STOP,
                retry_no_data=True,
                start_time=utcnow() - UPDATE_TIME_PERIOD,
            )
        except (NwsNoDataError, ClientResponseError) as err:
            if not self.last_api_success_time or (
                utcnow() - self.last_api_success_time > OBSERVATION_VALID_TIME
            ):
                raise UpdateFailed(err) from err
            _LOGGER.debug(
                "NWS observation update failed, but data still valid. Last success: %s",
                self.last_api_success_time,
            )
        else:
            self.last_api_success_time = utcnow()
