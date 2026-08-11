"""The National Weather Service integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import datetime
import logging

from pynws import NwsNoDataError, SimpleNWS, call_with_retry

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    EntityStateAttribute,
    Platform,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import debounce, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import (
    async_track_entity_registry_updated_event,
    async_track_state_change_event,
)
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


def get_base_unique_id(entry: ConfigEntry) -> str:
    """Return base unique id from config entry."""
    if entry.data.get(CONF_LOCATION_ENTITY):
        return entry.entry_id
    return base_unique_id(entry.data[CONF_LATITUDE], entry.data[CONF_LONGITUDE])


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
    api_key = entry.data[CONF_API_KEY]
    location_entity_id: str | None = None

    if location_registry_id := entry.data.get(CONF_LOCATION_ENTITY):
        registry = er.async_get(hass)
        entity_entry = registry.async_get(location_registry_id)
        if entity_entry is None:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="entity_not_found",
            )
        if entity_entry.disabled_by is not None:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="entity_disabled",
            )
        location_entity_id = entity_entry.entity_id
        state = hass.states.get(location_entity_id)
        if state is None or not has_location(state):
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="entity_unavailable",
                translation_placeholders={"entity_id": location_entity_id},
            )
        latitude = state.attributes[EntityStateAttribute.LATITUDE]
        longitude = state.attributes[EntityStateAttribute.LONGITUDE]
        station = None
    else:
        latitude = entry.data[CONF_LATITUDE]
        longitude = entry.data[CONF_LONGITUDE]
        station = entry.data[CONF_STATION]

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
                    entry.runtime_data.api.update_forecast,
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
                    entry.runtime_data.api.update_forecast_hourly,
                    retry_interval,
                    retry_stop,
                    retry_no_data=True,
                )
            except NwsNoDataError as err:
                raise UpdateFailed("No data returned.") from err

        return update_forecast_hourly

    coordinator_observation = NWSObservationDataUpdateCoordinator(
        hass,
        entry,
        nws_data,
        location_entity_id=location_entity_id,
        initial_position=(latitude, longitude) if location_entity_id else None,
    )

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
        def _async_on_location_state_change(
            event: Event[EventStateChangedData],
        ) -> None:
            """Request coordinator refresh when the location entity moves."""
            new_state = event.data["new_state"]
            if new_state is None or not has_location(new_state):
                return
            new_lat = new_state.attributes[EntityStateAttribute.LATITUDE]
            new_lon = new_state.attributes[EntityStateAttribute.LONGITUDE]
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
            if dist is not None and dist <= LOCATION_CHANGE_THRESHOLD:
                return
            entry.async_create_task(hass, coordinator_observation.async_refresh())

        entry.async_on_unload(
            async_track_state_change_event(
                hass, location_entity_id, _async_on_location_state_change
            )
        )

        @callback
        def _async_on_entity_registry_update(
            event: Event[er.EventEntityRegistryUpdatedData],
        ) -> None:
            """Reload when the tracked entity is renamed, removed, or disabled."""
            if event.data["action"] == "remove" or (
                event.data["action"] == "update"
                and (
                    "entity_id" in event.data["changes"]
                    or "disabled_by" in event.data["changes"]
                )
            ):
                hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))

        entry.async_on_unload(
            async_track_entity_registry_updated_event(
                hass, [location_entity_id], _async_on_entity_registry_update
            )
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NWSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def device_info(entry: ConfigEntry, nws_data: NWSData) -> DeviceInfo:
    """Return device registry information."""
    uid = get_base_unique_id(entry)
    if nws_data.location_entity_id:
        name = f"NWS: {nws_data.location_entity_id}"
    else:
        name = f"NWS: {entry.data[CONF_LATITUDE]}, {entry.data[CONF_LONGITUDE]}"
    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, uid)},
        manufacturer="National Weather Service",
        name=name,
    )
