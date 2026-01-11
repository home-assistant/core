"""Support for Google travel time sensors."""

from __future__ import annotations

import datetime
import logging
from typing import Any

from google.api_core.client_options import ClientOptions
from google.api_core.exceptions import GoogleAPIError, PermissionDenied
from google.maps.routing_v2 import Route, RoutesAsyncClient

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
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
    TRAVEL_MODES_TO_GOOGLE_SDK_ENUM,
)
from .helpers import (
    async_compute_routes,
    create_routes_api_disabled_issue,
    delete_routes_api_disabled_issue,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=10)
FIELD_MASK = "routes.duration,routes.localized_values"

SENSOR_DESCRIPTIONS = [
    SensorEntityDescription(
        key="duration",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
    )
]


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

    sensors = [
        GoogleTravelTimeSensor(
            config_entry, name, api_key, origin, destination, client, sensor_description
        )
        for sensor_description in SENSOR_DESCRIPTIONS
    ]

    async_add_entities(sensors, False)


class GoogleTravelTimeSensor(SensorEntity):
    """Representation of a Google travel time sensor."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        config_entry: ConfigEntry,
        name: str,
        api_key: str,
        origin: str,
        destination: str,
        client: RoutesAsyncClient,
        sensor_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = sensor_description
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

        return self._route.duration.seconds

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

        self._resolved_origin = find_coordinates(self.hass, self._origin)
        self._resolved_destination = find_coordinates(self.hass, self._destination)
        _LOGGER.debug(
            "Getting update for origin: %s destination: %s",
            self._resolved_origin,
            self._resolved_destination,
        )
        if self._resolved_destination is not None and self._resolved_origin is not None:
            try:
                response = await async_compute_routes(
                    client=self._client,
                    origin=self._resolved_origin,
                    destination=self._resolved_destination,
                    hass=self.hass,
                    travel_mode=travel_mode,
                    units=self._config_entry.options[CONF_UNITS],
                    language=self._config_entry.options.get(CONF_LANGUAGE),
                    avoid=self._config_entry.options.get(CONF_AVOID),
                    traffic_model=self._config_entry.options.get(CONF_TRAFFIC_MODEL),
                    transit_mode=self._config_entry.options.get(CONF_TRANSIT_MODE),
                    transit_routing_preference=self._config_entry.options.get(
                        CONF_TRANSIT_ROUTING_PREFERENCE
                    ),
                    departure_time=self._config_entry.options.get(CONF_DEPARTURE_TIME),
                    arrival_time=self._config_entry.options.get(CONF_ARRIVAL_TIME),
                    field_mask=FIELD_MASK,
                )
                _LOGGER.debug("Received response: %s", response)
                if response is not None and len(response.routes) > 0:
                    self._route = response.routes[0]
                delete_routes_api_disabled_issue(self.hass, self._config_entry)
            except PermissionDenied:
                _LOGGER.error("Routes API is disabled for this API key")
                create_routes_api_disabled_issue(self.hass, self._config_entry)
                self._route = None
            except GoogleAPIError as ex:
                _LOGGER.error("Error getting travel time: %s", ex)
                self._route = None
