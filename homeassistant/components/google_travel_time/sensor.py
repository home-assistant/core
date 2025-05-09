"""Support for Google travel time sensors."""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Any

from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import GoogleAPIError
from google.maps.routing_v2 import (
    ComputeRoutesRequest,
    Route,
    RouteModifiers,
    RoutesAsyncClient,
    RouteTravelMode,
    RoutingPreference,
    TransitPreferences,
)
from google.protobuf import timestamp_pb2

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LANGUAGE,
    CONF_MODE,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STARTED,
    UnitOfTime,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.location import find_coordinates
from homeassistant.util import dt as dt_util

from .const import (
    ATTRIBUTION,
    CONF_ARRIVAL_TIME,
    CONF_AVOID,
    CONF_DEPARTURE_TIME,
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_TRAFFIC_MODEL,
    CONF_TRANSIT_MODE,
    CONF_TRANSIT_ROUTING_PREFERENCE,
    CONF_UNITS,
    DEFAULT_NAME,
    DOMAIN,
    TRAFFIC_MODELS_TO_GOOGLE_SDK_ENUM,
    TRANSIT_PREFS_TO_GOOGLE_SDK_ENUM,
    TRANSPORT_TYPES_TO_GOOGLE_SDK_ENUM,
    TRAVEL_MODES_TO_GOOGLE_SDK_ENUM,
    UNITS_TO_GOOGLE_SDK_ENUM,
)
from .helpers import convert_to_waypoint

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=10)
FIELD_MASK = "routes.duration,routes.localized_values"


def convert_time(time_str: str) -> timestamp_pb2.Timestamp | None:
    """Convert a string like '08:00' to a google pb2 Timestamp.

    If the time is in the past, it will be shifted to the next day.
    """
    parsed_time = dt_util.parse_time(time_str)
    if TYPE_CHECKING:
        assert parsed_time is not None
    start_of_day = dt_util.start_of_local_day()
    combined = datetime.datetime.combine(
        start_of_day,
        parsed_time,
        start_of_day.tzinfo,
    )
    if combined < dt_util.now():
        combined = combined + datetime.timedelta(days=1)
    timestamp = timestamp_pb2.Timestamp()
    timestamp.FromDatetime(dt=combined)
    return timestamp


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Google travel time sensor entry."""
    api_key = config_entry.data[CONF_API_KEY]
    origin = config_entry.data[CONF_ORIGIN]
    destination = config_entry.data[CONF_DESTINATION]
    name = config_entry.data.get(CONF_NAME, DEFAULT_NAME)

    client_options = ClientOptions(api_key=api_key)
    client = RoutesAsyncClient(client_options=client_options)

    sensor = GoogleTravelTimeSensor(
        config_entry, name, api_key, origin, destination, client
    )

    async_add_entities([sensor], False)


class GoogleTravelTimeSensor(SensorEntity):
    """Representation of a Google travel time sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        config_entry: ConfigEntry,
        name: str,
        api_key: str,
        origin: str,
        destination: str,
        client: RoutesAsyncClient,
    ) -> None:
        """Initialize the sensor."""
        self._attr_name = name
        self._attr_unique_id = config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, api_key)},
            name=DOMAIN,
        )

        self._config_entry = config_entry
        self._route: Route | None = None
        self._client = client
        self._origin = origin
        self._destination = destination
        self._resolved_origin: str | None = None
        self._resolved_destination: str | None = None

    async def async_added_to_hass(self) -> None:
        """Handle when entity is added."""
        if self.hass.state is not CoreState.running:
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, self.first_update
            )
        else:
            await self.first_update()

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self._route is None:
            return None

        return round(self._route.duration.seconds / 60)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if self._route is None:
            return None

        result = self._config_entry.options.copy()
        result["duration_in_traffic"] = self._route.localized_values.duration.text
        result["duration"] = self._route.localized_values.static_duration.text
        result["distance"] = self._route.localized_values.distance.text

        result["origin"] = self._resolved_origin
        result["destination"] = self._resolved_destination
        return result

    async def first_update(self, _=None) -> None:
        """Run the first update and write the state."""
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Get the latest data from Google."""
        travel_mode = TRAVEL_MODES_TO_GOOGLE_SDK_ENUM[
            self._config_entry.options[CONF_MODE]
        ]

        if (
            departure_time := self._config_entry.options.get(CONF_DEPARTURE_TIME)
        ) is not None:
            departure_time = convert_time(departure_time)

        if (
            arrival_time := self._config_entry.options.get(CONF_ARRIVAL_TIME)
        ) is not None:
            arrival_time = convert_time(arrival_time)
        if travel_mode != RouteTravelMode.TRANSIT:
            arrival_time = None

        traffic_model = None
        routing_preference = None
        route_modifiers = None
        if travel_mode == RouteTravelMode.DRIVE:
            if (
                options_traffic_model := self._config_entry.options.get(
                    CONF_TRAFFIC_MODEL
                )
            ) is not None:
                traffic_model = TRAFFIC_MODELS_TO_GOOGLE_SDK_ENUM[options_traffic_model]
            routing_preference = RoutingPreference.TRAFFIC_AWARE_OPTIMAL
            route_modifiers = RouteModifiers(
                avoid_tolls=self._config_entry.options.get(CONF_AVOID) == "tolls",
                avoid_ferries=self._config_entry.options.get(CONF_AVOID) == "ferries",
                avoid_highways=self._config_entry.options.get(CONF_AVOID) == "highways",
                avoid_indoor=self._config_entry.options.get(CONF_AVOID) == "indoor",
            )

        transit_preferences = None
        if travel_mode == RouteTravelMode.TRANSIT:
            transit_routing_preference = None
            transit_travel_mode = (
                TransitPreferences.TransitTravelMode.TRANSIT_TRAVEL_MODE_UNSPECIFIED
            )
            if (
                option_transit_preferences := self._config_entry.options.get(
                    CONF_TRANSIT_ROUTING_PREFERENCE
                )
            ) is not None:
                transit_routing_preference = TRANSIT_PREFS_TO_GOOGLE_SDK_ENUM[
                    option_transit_preferences
                ]
            if (
                option_transit_mode := self._config_entry.options.get(CONF_TRANSIT_MODE)
            ) is not None:
                transit_travel_mode = TRANSPORT_TYPES_TO_GOOGLE_SDK_ENUM[
                    option_transit_mode
                ]
            transit_preferences = TransitPreferences(
                routing_preference=transit_routing_preference,
                allowed_travel_modes=[transit_travel_mode],
            )

        language = None
        if (
            options_language := self._config_entry.options.get(CONF_LANGUAGE)
        ) is not None:
            language = options_language

        self._resolved_origin = find_coordinates(self.hass, self._origin)
        self._resolved_destination = find_coordinates(self.hass, self._destination)
        _LOGGER.debug(
            "Getting update for origin: %s destination: %s",
            self._resolved_origin,
            self._resolved_destination,
        )
        if self._resolved_destination is not None and self._resolved_origin is not None:
            request = ComputeRoutesRequest(
                origin=convert_to_waypoint(self.hass, self._resolved_origin),
                destination=convert_to_waypoint(self.hass, self._resolved_destination),
                travel_mode=travel_mode,
                routing_preference=routing_preference,
                departure_time=departure_time,
                arrival_time=arrival_time,
                route_modifiers=route_modifiers,
                language_code=language,
                units=UNITS_TO_GOOGLE_SDK_ENUM[self._config_entry.options[CONF_UNITS]],
                traffic_model=traffic_model,
                transit_preferences=transit_preferences,
            )
            try:
                response = await self._client.compute_routes(
                    request, metadata=[("x-goog-fieldmask", FIELD_MASK)]
                )
                if response is not None and len(response.routes) > 0:
                    self._route = response.routes[0]
            except GoogleAPIError as ex:
                _LOGGER.error("Error getting travel time: %s", ex)
                self._route = None
