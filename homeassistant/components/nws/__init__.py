"""The National Weather Service integration."""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
import datetime
import logging
from typing import Any

from pynws import NwsNoDataError, SimpleNWS, call_with_retry

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    Platform,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import debounce, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.location import has_location
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import location as location_util

from .const import (
    CONF_LOCATION_ENTITY,
    CONF_STATION,
    DEBOUNCE_TIME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOCATION_CHANGE_THRESHOLD,
    RETRY_INTERVAL,
    RETRY_STOP,
)
from .coordinator import NWSObservationDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.WEATHER]

type NWSConfigEntry = ConfigEntry[NWSData]


def base_unique_id(latitude: float, longitude: float) -> str:
    """Return unique id for entries in configuration."""
    return f"{latitude}_{longitude}"


def get_base_unique_id(entry_data: Mapping[str, Any]) -> str:
    """Return base unique id from config entry data."""
    if location_entity := entry_data.get(CONF_LOCATION_ENTITY):
        return f"entity_{location_entity}"
    return base_unique_id(entry_data[CONF_LATITUDE], entry_data[CONF_LONGITUDE])


@dataclass
class NWSData:
    """Data for the National Weather Service integration."""

    api: SimpleNWS
    coordinator_observation: NWSObservationDataUpdateCoordinator
    coordinator_forecast: TimestampDataUpdateCoordinator[None]
    coordinator_forecast_hourly: TimestampDataUpdateCoordinator[None]
    latitude: float
    longitude: float
    location_entity_id: str | None


async def async_setup_entry(hass: HomeAssistant, entry: NWSConfigEntry) -> bool:
    """Set up a National Weather Service entry."""
    latitude = entry.data[CONF_LATITUDE]
    longitude = entry.data[CONF_LONGITUDE]
    api_key = entry.data[CONF_API_KEY]
    station = entry.data.get(CONF_STATION)
    location_entity_id: str | None = None
    if location_registry_id := entry.data.get(CONF_LOCATION_ENTITY):
        registry = er.async_get(hass)
        entity_entry = registry.async_get(location_registry_id)
        if entity_entry is not None:
            location_entity_id = entity_entry.entity_id
            state = hass.states.get(location_entity_id)
            if state is not None and has_location(state):
                latitude = state.attributes[ATTR_LATITUDE]
                longitude = state.attributes[ATTR_LONGITUDE]
            else:
                _LOGGER.warning(
                    "Location entity %s is not available, using stored coordinates",
                    location_entity_id,
                )
        else:
            _LOGGER.warning(
                "Location entity registry ID %s not found, using stored coordinates",
                location_registry_id,
            )

    client_session = async_get_clientsession(hass)

    # set_station only does IO when station is None
    nws_data = SimpleNWS(latitude, longitude, api_key, client_session)
    await nws_data.set_station(station)

    def async_setup_update_forecast(
        retry_interval: datetime.timedelta | float,
        retry_stop: datetime.timedelta | float,
    ) -> Callable[[], Awaitable[None]]:
        async def update_forecast() -> None:
            """Retrieve forecast."""
            try:
                await call_with_retry(
                    nws_data.update_forecast,
                    retry_interval,
                    retry_stop,
                    retry_no_data=True,
                )
            except NwsNoDataError as err:
                raise UpdateFailed("No data returned.") from err

        return update_forecast

    def async_setup_update_forecast_hourly(
        retry_interval: datetime.timedelta | float,
        retry_stop: datetime.timedelta | float,
    ) -> Callable[[], Awaitable[None]]:
        async def update_forecast_hourly() -> None:
            """Retrieve forecast hourly."""
            try:
                await call_with_retry(
                    nws_data.update_forecast_hourly,
                    retry_interval,
                    retry_stop,
                    retry_no_data=True,
                )
            except NwsNoDataError as err:
                raise UpdateFailed("No data returned.") from err

        return update_forecast_hourly

    coordinator_observation = NWSObservationDataUpdateCoordinator(hass, entry, nws_data)

    # Don't use retries in setup
    coordinator_forecast = TimestampDataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=f"NWS forecast station {nws_data.station}",
        update_method=async_setup_update_forecast(0, 0),
        update_interval=DEFAULT_SCAN_INTERVAL,
        request_refresh_debouncer=debounce.Debouncer(
            hass, _LOGGER, cooldown=DEBOUNCE_TIME, immediate=True
        ),
    )

    coordinator_forecast_hourly = TimestampDataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=f"NWS forecast hourly station {nws_data.station}",
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
        latitude,
        longitude,
        location_entity_id,
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator_observation.async_refresh()
    await coordinator_forecast.async_refresh()
    await coordinator_forecast_hourly.async_refresh()

    # Use retries
    coordinator_forecast.update_method = async_setup_update_forecast(
        RETRY_INTERVAL, RETRY_STOP
    )
    coordinator_forecast_hourly.update_method = async_setup_update_forecast_hourly(
        RETRY_INTERVAL, RETRY_STOP
    )

    if location_entity_id:

        @callback
        def _async_handle_location_change(event: Event[EventStateChangedData]) -> None:
            """Handle location entity state changes."""
            new_state = event.data["new_state"]
            if new_state is None or not has_location(new_state):
                return
            new_lat = new_state.attributes[ATTR_LATITUDE]
            new_lon = new_state.attributes[ATTR_LONGITUDE]
            if (
                new_lat == entry.runtime_data.latitude
                and new_lon == entry.runtime_data.longitude
            ):
                return
            dist = location_util.distance(
                entry.runtime_data.latitude,
                entry.runtime_data.longitude,
                new_lat,
                new_lon,
            )
            if dist is not None and dist > LOCATION_CHANGE_THRESHOLD:
                _LOGGER.info(
                    "Location entity %s moved %.0f m, reloading NWS",
                    location_entity_id,
                    dist,
                )
                hass.config_entries.async_schedule_reload(entry.entry_id)

        entry.async_on_unload(
            async_track_state_change_event(
                hass, location_entity_id, _async_handle_location_change
            )
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NWSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def device_info(entry_data: Mapping[str, Any], nws_data: NWSData) -> DeviceInfo:
    """Return device registry information."""
    uid = get_base_unique_id(entry_data)
    if nws_data.location_entity_id:
        name = f"NWS: {nws_data.location_entity_id}"
    else:
        name = f"NWS: {entry_data[CONF_LATITUDE]}, {entry_data[CONF_LONGITUDE]}"
    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, uid)},
        manufacturer="National Weather Service",
        name=name,
    )
