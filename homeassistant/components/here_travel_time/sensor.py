"""Support for HERE travel time sensors."""
from __future__ import annotations

from datetime import timedelta
import logging

import herepy
from herepy.here_enum import RouteMode
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_MODE,
    CONF_API_KEY,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
    TIME_MINUTES,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HereTravelTimeDataUpdateCoordinator
from .model import HERETravelTimeConfig

_LOGGER = logging.getLogger(__name__)

CONF_DESTINATION_LATITUDE = "destination_latitude"
CONF_DESTINATION_LONGITUDE = "destination_longitude"
CONF_DESTINATION_ENTITY_ID = "destination_entity_id"
CONF_ORIGIN_LATITUDE = "origin_latitude"
CONF_ORIGIN_LONGITUDE = "origin_longitude"
CONF_ORIGIN_ENTITY_ID = "origin_entity_id"
CONF_TRAFFIC_MODE = "traffic_mode"
CONF_ROUTE_MODE = "route_mode"
CONF_ARRIVAL = "arrival"
CONF_DEPARTURE = "departure"

DEFAULT_NAME = "HERE Travel Time"

TRAVEL_MODE_BICYCLE = "bicycle"
TRAVEL_MODE_CAR = "car"
TRAVEL_MODE_PEDESTRIAN = "pedestrian"
TRAVEL_MODE_PUBLIC = "publicTransport"
TRAVEL_MODE_PUBLIC_TIME_TABLE = "publicTransportTimeTable"
TRAVEL_MODE_TRUCK = "truck"
TRAVEL_MODE = [
    TRAVEL_MODE_BICYCLE,
    TRAVEL_MODE_CAR,
    TRAVEL_MODE_PEDESTRIAN,
    TRAVEL_MODE_PUBLIC,
    TRAVEL_MODE_PUBLIC_TIME_TABLE,
    TRAVEL_MODE_TRUCK,
]

TRAVEL_MODES_PUBLIC = [TRAVEL_MODE_PUBLIC, TRAVEL_MODE_PUBLIC_TIME_TABLE]
TRAVEL_MODES_VEHICLE = [TRAVEL_MODE_CAR, TRAVEL_MODE_TRUCK]
TRAVEL_MODES_NON_VEHICLE = [TRAVEL_MODE_BICYCLE, TRAVEL_MODE_PEDESTRIAN]

TRAFFIC_MODE_ENABLED = "traffic_enabled"
TRAFFIC_MODE_DISABLED = "traffic_disabled"

ROUTE_MODE_FASTEST = "fastest"
ROUTE_MODE_SHORTEST = "shortest"
ROUTE_MODE = [ROUTE_MODE_FASTEST, ROUTE_MODE_SHORTEST]

ICON_BICYCLE = "mdi:bike"
ICON_CAR = "mdi:car"
ICON_PEDESTRIAN = "mdi:walk"
ICON_PUBLIC = "mdi:bus"
ICON_TRUCK = "mdi:truck"

UNITS = [CONF_UNIT_SYSTEM_METRIC, CONF_UNIT_SYSTEM_IMPERIAL]

ATTR_DURATION = "duration"
ATTR_DISTANCE = "distance"
ATTR_ROUTE = "route"
ATTR_ORIGIN = "origin"
ATTR_DESTINATION = "destination"

ATTR_UNIT_SYSTEM = CONF_UNIT_SYSTEM
ATTR_TRAFFIC_MODE = CONF_TRAFFIC_MODE

ATTR_DURATION_IN_TRAFFIC = "duration_in_traffic"
ATTR_ORIGIN_NAME = "origin_name"
ATTR_DESTINATION_NAME = "destination_name"

SCAN_INTERVAL = timedelta(minutes=5)

NO_ROUTE_ERROR_MESSAGE = "HERE could not find a route based on the input"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Inclusive(
            CONF_DESTINATION_LATITUDE, "destination_coordinates"
        ): cv.latitude,
        vol.Inclusive(
            CONF_DESTINATION_LONGITUDE, "destination_coordinates"
        ): cv.longitude,
        vol.Exclusive(CONF_DESTINATION_LATITUDE, "destination"): cv.latitude,
        vol.Exclusive(CONF_DESTINATION_ENTITY_ID, "destination"): cv.entity_id,
        vol.Inclusive(CONF_ORIGIN_LATITUDE, "origin_coordinates"): cv.latitude,
        vol.Inclusive(CONF_ORIGIN_LONGITUDE, "origin_coordinates"): cv.longitude,
        vol.Exclusive(CONF_ORIGIN_LATITUDE, "origin"): cv.latitude,
        vol.Exclusive(CONF_ORIGIN_ENTITY_ID, "origin"): cv.entity_id,
        vol.Optional(CONF_DEPARTURE): cv.time,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODE, default=TRAVEL_MODE_CAR): vol.In(TRAVEL_MODE),
        vol.Optional(CONF_ROUTE_MODE, default=ROUTE_MODE_FASTEST): vol.In(ROUTE_MODE),
        vol.Optional(CONF_TRAFFIC_MODE, default=False): cv.boolean,
        vol.Optional(CONF_UNIT_SYSTEM): vol.In(UNITS),
    }
)

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_DESTINATION_LATITUDE, CONF_DESTINATION_ENTITY_ID),
    cv.has_at_least_one_key(CONF_ORIGIN_LATITUDE, CONF_ORIGIN_ENTITY_ID),
    cv.key_value_schemas(
        CONF_MODE,
        {
            None: PLATFORM_SCHEMA,
            TRAVEL_MODE_BICYCLE: PLATFORM_SCHEMA,
            TRAVEL_MODE_CAR: PLATFORM_SCHEMA,
            TRAVEL_MODE_PEDESTRIAN: PLATFORM_SCHEMA,
            TRAVEL_MODE_PUBLIC: PLATFORM_SCHEMA,
            TRAVEL_MODE_TRUCK: PLATFORM_SCHEMA,
            TRAVEL_MODE_PUBLIC_TIME_TABLE: PLATFORM_SCHEMA.extend(
                {
                    vol.Exclusive(CONF_ARRIVAL, "arrival_departure"): cv.time,
                    vol.Exclusive(CONF_DEPARTURE, "arrival_departure"): cv.time,
                }
            ),
        },
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the HERE travel time platform."""
    api_key = config[CONF_API_KEY]
    here_client = herepy.RoutingApi(api_key)

    if not await hass.async_add_executor_job(
        _are_valid_client_credentials, here_client
    ):
        _LOGGER.error(
            "Invalid credentials. This error is returned if the specified token was invalid or no contract could be found for this token"
        )
        return

    if config.get(CONF_ORIGIN_LATITUDE) is not None:
        origin = f"{config[CONF_ORIGIN_LATITUDE]},{config[CONF_ORIGIN_LONGITUDE]}"
        origin_entity_id = None
    else:
        origin = None
        origin_entity_id = config[CONF_ORIGIN_ENTITY_ID]

    if config.get(CONF_DESTINATION_LATITUDE) is not None:
        destination = (
            f"{config[CONF_DESTINATION_LATITUDE]},{config[CONF_DESTINATION_LONGITUDE]}"
        )
        destination_entity_id = None
    else:
        destination = None
        destination_entity_id = config[CONF_DESTINATION_ENTITY_ID]

    traffic_mode = config[CONF_TRAFFIC_MODE]
    name = config[CONF_NAME]

    here_travel_time_config = HERETravelTimeConfig(
        origin=origin,
        destination=destination,
        origin_entity_id=origin_entity_id,
        destination_entity_id=destination_entity_id,
        travel_mode=config[CONF_MODE],
        route_mode=config[CONF_ROUTE_MODE],
        units=config.get(CONF_UNIT_SYSTEM, hass.config.units.name),
        arrival=config.get(CONF_ARRIVAL),
        departure=config.get(CONF_DEPARTURE),
    )

    coordinator = HereTravelTimeDataUpdateCoordinator(
        hass,
        here_client,
        here_travel_time_config,
    )

    sensor = HERETravelTimeSensor(name, traffic_mode, coordinator)

    async_add_entities([sensor])


def _are_valid_client_credentials(here_client: herepy.RoutingApi) -> bool:
    """Check if the provided credentials are correct using defaults."""
    known_working_origin = [38.9, -77.04833]
    known_working_destination = [39.0, -77.1]
    try:
        here_client.public_transport_timetable(
            known_working_origin,
            known_working_destination,
            True,
            [
                RouteMode[ROUTE_MODE_FASTEST],
                RouteMode[TRAVEL_MODE_CAR],
                RouteMode[TRAFFIC_MODE_ENABLED],
            ],
            arrival=None,
            departure="now",
        )
    except herepy.InvalidCredentialsError:
        return False
    return True


class HERETravelTimeSensor(SensorEntity, CoordinatorEntity):
    """Representation of a HERE travel time sensor."""

    def __init__(
        self,
        name: str,
        traffic_mode: bool,
        coordinator: HereTravelTimeDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._traffic_mode = traffic_mode
        self._attr_native_unit_of_measurement = TIME_MINUTES
        self._attr_name = name

    async def async_added_to_hass(self) -> None:
        """Wait for start so origin and destination entities can be resolved."""
        await super().async_added_to_hass()

        async def _update_at_start(_):
            await self.async_update()

        self.async_on_remove(async_at_start(self.hass, _update_at_start))

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.data is not None:
            return str(
                round(
                    self.coordinator.data.get(
                        ATTR_DURATION_IN_TRAFFIC
                        if self._traffic_mode
                        else ATTR_DURATION
                    )
                )
            )
        return None

    @property
    def extra_state_attributes(
        self,
    ) -> dict[str, None | float | str | bool] | None:
        """Return the state attributes."""
        if self.coordinator.data is not None:
            res = {
                ATTR_UNIT_SYSTEM: self.coordinator.config.units,
                ATTR_MODE: self.coordinator.config.travel_mode,
                ATTR_TRAFFIC_MODE: self._traffic_mode,
                **self.coordinator.data,
            }
            res.pop(ATTR_ATTRIBUTION)
            return res
        return None

    @property
    def attribution(self) -> str | None:
        """Return the attribution."""
        if self.coordinator.data is not None:
            return self.coordinator.data.get(ATTR_ATTRIBUTION)

    @property
    def icon(self) -> str:
        """Icon to use in the frontend depending on travel_mode."""
        if self.coordinator.config.travel_mode == TRAVEL_MODE_BICYCLE:
            return ICON_BICYCLE
        if self.coordinator.config.travel_mode == TRAVEL_MODE_PEDESTRIAN:
            return ICON_PEDESTRIAN
        if self.coordinator.config.travel_mode in TRAVEL_MODES_PUBLIC:
            return ICON_PUBLIC
        if self.coordinator.config.travel_mode == TRAVEL_MODE_TRUCK:
            return ICON_TRUCK
        return ICON_CAR
