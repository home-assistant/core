"""Support for HERE travel time sensors."""
from datetime import datetime, timedelta
import logging
from typing import Callable, Dict, Optional, Union

import herepy
import voluptuous as vol

from homeassistant.components.travel_time import TRAVEL_TIME_SCHEMA, TravelTimeEntity
from homeassistant.components.travel_time.const import (
    CONF_DESTINATION_ENTITY_ID,
    CONF_DESTINATION_LATITUDE,
    CONF_DESTINATION_LONGITUDE,
    CONF_ORIGIN_ENTITY_ID,
    CONF_ORIGIN_LATITUDE,
    CONF_ORIGIN_LONGITUDE,
    CONF_TRAVEL_MODE,
    CONF_ROUTE_MODE,
    CONF_TRAFFIC_MODE,
    ICON_BICYCLE,
    ICON_CAR,
    ICON_PEDESTRIAN,
    ICON_PUBLIC,
    ICON_TRUCK,
    UNIT_OF_MEASUREMENT,
)
from homeassistant.const import (
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
    EVENT_HOMEASSISTANT_START,
    TIME_MINUTES,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import DiscoveryInfoType
import homeassistant.util.dt as dt

_LOGGER = logging.getLogger(__name__)

CONF_DESTINATION_LATITUDE = "destination_latitude"
CONF_DESTINATION_LATITUDE_TEMPLATE = "destination_latitude_template"
CONF_DESTINATION_LONGITUDE = "destination_longitude"
CONF_DESTINATION_LONGITUDE_TEMPLATE = "destination_longitude_template"
CONF_ORIGIN_LATITUDE = "origin_latitude"
CONF_ORIGIN_LATITUDE_TEMPLATE = "origin_latitude_template"
CONF_ORIGIN_LONGITUDE = "origin_longitude"
CONF_ORIGIN_LONGITUDE_TEMPLATE = "origin_longitude_template"
CONF_API_KEY = "api_key"
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
    config: Dict[str, Union[str, bool]],
    async_add_entities: Callable,
    discovery_info: Optional[DiscoveryInfoType] = None,
) -> None:
    """Set up the HERE travel time platform."""

    api_key = config[CONF_API_KEY]
    here_client = herepy.RoutingApi(api_key)

    if not await hass.async_add_executor_job(
        _are_valid_client_credentials, here_client
    ):
        _LOGGER.error(
            "Invalid credentials. This error is returned if the specified token was invalid or no contract could be found for this token."
        )
        return

    # TODO CHANGE TO TEMPLATE
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

    travel_mode = config[CONF_MODE]
    traffic_mode = config[CONF_TRAFFIC_MODE]
    route_mode = config[CONF_ROUTE_MODE]
    name = config[CONF_NAME]
    units = config.get(CONF_UNIT_SYSTEM, hass.config.units.name)
    arrival = config.get(CONF_ARRIVAL)
    departure = config.get(CONF_DEPARTURE)

    here_data = HERETravelTimeData(
        here_client, travel_mode, traffic_mode, route_mode, units, arrival, departure
    )

    travel_time_entity = HERETravelTimeEntity(
        name, origin, destination, origin_entity_id, destination_entity_id, here_data
    )

    async_add_entities([travel_time_entity])


def _are_valid_client_credentials(here_client: herepy.RoutingApi) -> bool:
    """Check if the provided credentials are correct using defaults."""
    known_working_origin = [38.9, -77.04833]
    known_working_destination = [39.0, -77.1]
    try:
        here_client.car_route(
            known_working_origin,
            known_working_destination,
            [
                herepy.RouteMode[ROUTE_MODE_FASTEST],
                herepy.RouteMode[TRAVEL_MODE_CAR],
                herepy.RouteMode[TRAFFIC_MODE_DISABLED],
            ],
        )
    except herepy.InvalidCredentialsError:
        return False
    return True


class HERETravelTimeEntity(TravelTimeEntity):
    """Representation of HERE travel_time."""

    def __init__(
        self,
        name: str,
        origin: str,
        destination: str,
        origin_entity_id: str,
        destination_entity_id: str,
        here_data: "HERETravelTimeData",
    ) -> None:
        """Initialize the travel_time entity."""
        self._name = name
        self._origin_entity_id = origin_entity_id
        self._destination_entity_id = destination_entity_id
        self._here_data = here_data
        self._unit_of_measurement = TIME_MINUTES
        self._attrs = {
            ATTR_UNIT_SYSTEM: self._here_data.units,
            ATTR_MODE: self._here_data.travel_mode,
            ATTR_TRAFFIC_MODE: self._here_data.traffic_mode,
        }
        if self._origin_entity_id is None:
            self._here_data.origin = origin

        if self._destination_entity_id is None:
            self._here_data.destination = destination

    async def async_added_to_hass(self) -> None:
        """Delay the travel_time update to avoid entity not found warnings."""

        @callback
        def delayed_sensor_update(event):
            """Update sensor after Home Assistant started."""
            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, delayed_travel_time_update
        )

    @property
    def attribution(self) -> str:
        """Get the attribution of the travel_time entity."""
        if self._here_data.base_time is not None:
            return self._here_data.attribution

    @property
    def destination(self) -> str:
        """Get the destination coordinates of the travel_time entity."""
        if self._here_data.base_time is not None:
            return self._here_data.destination

    @property
    def destination_name(self) -> str:
        """Get the destination name of the travel_time entity."""
        if self._here_data.base_time is not None:
            return self._here_data.destination_name

    @property
    def distance(self) -> str:
        """Get the distance of the travel_time entity."""
        if self._here_data.base_time is not None:
            return self._here_data.distance

    @property
    def duration(self) -> str:
        """Get the duration without traffic of the travel_time entity."""
        if self._here_data.base_time is not None:
            return self._here_data.base_time / 60

    @property
    def duration_in_traffic(self) -> str:
        """Get the duration with traffic of the travel_time entity."""
        if self._here_data.base_time is not None:
            return self._here_data.traffic_time / 60

    @property
    def icon(self) -> str:
        """Icon to use in the frontend depending on travel_mode."""
        if self._here_data.travel_mode == TRAVEL_MODE_BICYCLE:
            return ICON_BICYCLE
        if self._here_data.travel_mode == TRAVEL_MODE_PEDESTRIAN:
            return ICON_PEDESTRIAN
        if self._here_data.travel_mode in TRAVEL_MODES_PUBLIC:
            return ICON_PUBLIC
        if self._here_data.travel_mode == TRAVEL_MODE_TRUCK:
            return ICON_TRUCK
        return ICON_CAR

    @property
    def mode(self) -> str:
        """Get the mode of travelling e.g car for this entity."""
        if self._here_data.travel_mode is not None:
            return self._here_data.travel_mode

    @property
    def name(self) -> str:
        """Get the name of the travel_time entity."""
        return self._name

    @property
    def origin(self) -> str:
        """Get the origin coordinates of the travel_time entity."""
        if self._here_data.base_time is not None:
            return self._here_data.origin

    @property
    def origin_name(self) -> str:
        """Get the origin name of the travel_time entity."""
        if self._here_data.base_time is not None:
            return self._here_data.origin_name

    @property
    def route(self) -> str:
        """Get the route of the travel_time entity."""
        if self._here_data.base_time is not None:
            return self._here_data.route

    @property
    def route_mode(self) -> str:
        """Get the route of the travel_time entity."""
        if self._here_data.route_mode is not None:
            return self._here_data.route_mode

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor."""
        if self._here_data.traffic_mode:
            if self._here_data.traffic_time is not None:
                return str(round(self._here_data.traffic_time / 60))
        if self._here_data.base_time is not None:
            return str(round(self._here_data.base_time / 60))

        return None

    @property
    def traffic_mode(self) -> Optional[str]:
        """Return if traffic_mode is enabled for this travel_time entity."""
        if self._here_data.traffic_mode is not None:
            return self._here_data.traffic_mode

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def unit_system(self) -> str:
        """Get the unit system of the travel_time entity."""
        if self._here_data.base_time is not None:
            return self._here_data.units

    async def async_update(self) -> None:
        """Update Sensor Information."""
        # TODO render template

        await self.hass.async_add_executor_job(self._here_data.update)

    async def _get_location_from_entity(
        self, entity_id: str, recursion_history: Optional[list] = None
    ) -> Optional[str]:
        """Get the location from the entity state or attributes."""
        entity = self.hass.states.get(entity_id)

        if entity is None:
            _LOGGER.error("Unable to find entity %s", entity_id)
            return None

        # Check if the entity has location attributes
        if location.has_location(entity):
            return self._get_location_from_attributes(entity)

        # Check if device is in a zone
        zone_entity = self.hass.states.get(f"zone.{entity.state}")
        if location.has_location(zone_entity):
            _LOGGER.debug(
                "%s is in %s, getting zone location", entity_id, zone_entity.entity_id
            )
            return self._get_location_from_attributes(zone_entity)

        # Check if state is valid coordinate set
        if self._entity_state_is_valid_coordinate_set(entity.state):
            return entity.state

        # Resolve nested entity
        if recursion_history is None:
            recursion_history = []
        recursion_history.append(entity_id)
        if entity.state in recursion_history:
            _LOGGER.error(
                "Circular Reference detected. The state of %s has already been checked.",
                entity.state,
            )
            return None
        _LOGGER.debug("Getting nested entity for state: %s", entity.state)
        nested_entity = self.hass.states.get(entity.state)
        if nested_entity is not None:
            _LOGGER.debug("Resolving nested entity_id: %s", entity.state)
            return await self._get_location_from_entity(entity.state, recursion_history)

        _LOGGER.error(
            "The state of %s is not a valid set of coordinates: %s",
            entity_id,
            entity.state,
        )
        return None

    @staticmethod
    def _entity_state_is_valid_coordinate_set(state: str) -> bool:
        """Check that the given string is a valid set of coordinates."""
        schema = vol.Schema(cv.gps)
        try:
            coordinates = state.split(",")
            schema(coordinates)
            return True
        except (vol.MultipleInvalid):
            return False

    @staticmethod
    def _get_location_from_attributes(entity: State) -> str:
        """Get the lat/long string from an entities attributes."""
        attr = entity.attributes
        return f"{attr.get(ATTR_LATITUDE)},{attr.get(ATTR_LONGITUDE)}"


class HERETravelTimeData:
    """HERETravelTime data object."""

    def __init__(
        self,
        here_client: herepy.RoutingApi,
        travel_mode: str,
        traffic_mode: bool,
        route_mode: str,
        units: str,
        arrival: datetime,
        departure: datetime,
    ) -> None:
        """Initialize herepy."""
        self.origin = None
        self.destination = None
        self.travel_mode = travel_mode
        self.traffic_mode = traffic_mode
        self.route_mode = route_mode
        self.arrival = arrival
        self.departure = departure
        self.attribution = None
        self.traffic_time = None
        self.distance = None
        self.route = None
        self.base_time = None
        self.origin_name = None
        self.destination_name = None
        self.units = units
        self._client = here_client
        self.combine_change = True

    def update(self) -> None:
        """Get the latest data from HERE."""
        if self.traffic_mode:
            traffic_mode = TRAFFIC_MODE_ENABLED
        else:
            traffic_mode = TRAFFIC_MODE_DISABLED

        if self.destination is not None and self.origin is not None:
            # Convert location to HERE friendly location
            destination = self.destination.split(",")
            origin = self.origin.split(",")
            arrival = self.arrival
            if arrival is not None:
                arrival = convert_time_to_isodate(arrival)
            departure = self.departure
            if departure is not None:
                departure = convert_time_to_isodate(departure)

            _LOGGER.debug(
                "Requesting route for origin: %s, destination: %s, route_mode: %s, mode: %s, traffic_mode: %s, arrival: %s, departure: %s",
                origin,
                destination,
                herepy.RouteMode[self.route_mode],
                herepy.RouteMode[self.travel_mode],
                herepy.RouteMode[traffic_mode],
                arrival,
                departure,
            )

            try:
                response = self._client.public_transport_timetable(
                    origin,
                    destination,
                    self.combine_change,
                    [
                        herepy.RouteMode[self.route_mode],
                        herepy.RouteMode[self.travel_mode],
                        herepy.RouteMode[traffic_mode],
                    ],
                    arrival=arrival,
                    departure=departure,
                )
            except herepy.NoRouteFoundError:
                # Better error message for cryptic no route error codes
                _LOGGER.error(NO_ROUTE_ERROR_MESSAGE)
                return

            _LOGGER.debug("Raw response is: %s", response.response)

            # pylint: disable=no-member
            source_attribution = response.response.get("sourceAttribution")
            if source_attribution is not None:
                self.attribution = self._build_hass_attribution(source_attribution)
            # pylint: disable=no-member
            route = response.response["route"]
            summary = route[0]["summary"]
            waypoint = route[0]["waypoint"]
            self.base_time = summary["baseTime"]
            if self.travel_mode in TRAVEL_MODES_VEHICLE:
                self.traffic_time = summary["trafficTime"]
            else:
                self.traffic_time = self.base_time
            distance = summary["distance"]
            if self.units == CONF_UNIT_SYSTEM_IMPERIAL:
                # Convert to miles.
                self.distance = distance / 1609.344
            else:
                # Convert to kilometers
                self.distance = distance / 1000
            # pylint: disable=no-member
            self.route = response.route_short
            self.origin_name = waypoint[0]["mappedRoadName"]
            self.destination_name = waypoint[1]["mappedRoadName"]

    @staticmethod
    def _build_hass_attribution(source_attribution: Dict) -> Optional[str]:
        """Build a hass frontend ready string out of the sourceAttribution."""
        suppliers = source_attribution.get("supplier")
        if suppliers is not None:
            supplier_titles = []
            for supplier in suppliers:
                title = supplier.get("title")
                if title is not None:
                    supplier_titles.append(title)
            joined_supplier_titles = ",".join(supplier_titles)
            attribution = f"With the support of {joined_supplier_titles}. All information is provided without warranty of any kind."
            return attribution


def convert_time_to_isodate(timestr: str) -> str:
    """Take a string like 08:00:00 and combine it with the current date."""
    combined = datetime.combine(dt.start_of_local_day(), dt.parse_time(timestr))
    if combined < datetime.now():
        combined = combined + timedelta(days=1)
    return combined.isoformat()
