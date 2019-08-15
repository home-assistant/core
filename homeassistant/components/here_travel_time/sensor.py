"""Support for HERE travel time sensors."""
from datetime import timedelta
import logging
from typing import Callable, Dict, Optional, Union, List

import herepy
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import location
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_DESTINATION_LATITUDE = "destination_latitude"
CONF_DESTINATION_LONGITUDE = "destination_longitude"
CONF_DESTINATION_ENTITY_ID = "destination_entity_id"
CONF_ORIGIN_LATITUDE = "origin_latitude"
CONF_ORIGIN_LONGITUDE = "origin_longitude"
CONF_ORIGIN_ENTITY_ID = "origin_entity_id"
CONF_APP_ID = "app_id"
CONF_APP_CODE = "app_code"
CONF_TRAFFIC_MODE = "traffic_mode"
CONF_ROUTE_MODE = "route_mode"

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

TRAFFIC_MODE_ENABLED = "traffic:enabled"
TRAFFIC_MODE_DISABLED = "traffic:disabled"

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

ATTR_DURATION_IN_TRAFFIC = "duration_in_traffic"
ATTR_ORIGIN_NAME = "origin_name"
ATTR_DESTINATION_NAME = "destination_name"

UNIT_OF_MEASUREMENT = "min"

SCAN_INTERVAL = timedelta(minutes=5)

TRACKABLE_DOMAINS = ["device_tracker", "sensor", "zone", "person"]
DATA_KEY = "here_travel_time"

NO_ROUTE_ERRORS = ["NGEO_ERROR_GRAPH_DISCONNECTED", "NGEO_ERROR_ROUTE_NO_END_POINT"]
NO_ROUTE_ERROR_MESSAGE = "HERE could not find a route based on the input"

COORDINATE_SCHEMA = vol.Schema(
    {
        vol.Inclusive(CONF_DESTINATION_LATITUDE, "coordinates"): cv.latitude,
        vol.Inclusive(CONF_DESTINATION_LONGITUDE, "coordinates"): cv.longitude,
    }
)

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_DESTINATION_LATITUDE, CONF_DESTINATION_ENTITY_ID),
    cv.has_at_least_one_key(CONF_ORIGIN_LATITUDE, CONF_ORIGIN_ENTITY_ID),
    PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_APP_ID): cv.string,
            vol.Required(CONF_APP_CODE): cv.string,
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
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_MODE, default=TRAVEL_MODE_CAR): vol.In(TRAVEL_MODE),
            vol.Optional(CONF_ROUTE_MODE, default=ROUTE_MODE_FASTEST): vol.In(
                ROUTE_MODE
            ),
            vol.Optional(CONF_TRAFFIC_MODE, default=False): cv.boolean,
            vol.Optional(CONF_UNIT_SYSTEM): vol.In(UNITS),
        }
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: Dict[str, Union[str, bool]],
    async_add_entities: Callable,
    discovery_info: None = None,
) -> None:
    """Set up the HERE travel time platform."""
    hass.data.setdefault(DATA_KEY, [])

    app_id = config[CONF_APP_ID]
    app_code = config[CONF_APP_CODE]
    if config.get(CONF_ORIGIN_LATITUDE) is not None:
        origin = ",".join(
            [str(config[CONF_ORIGIN_LATITUDE]), str(config[CONF_ORIGIN_LONGITUDE])]
        )
    else:
        origin = config[CONF_ORIGIN_ENTITY_ID]

    if config.get(CONF_DESTINATION_LATITUDE) is not None:
        destination = ",".join(
            [
                str(config[CONF_DESTINATION_LATITUDE]),
                str(config[CONF_DESTINATION_LONGITUDE]),
            ]
        )
    else:
        destination = config[CONF_DESTINATION_ENTITY_ID]

    travel_mode = config.get(CONF_MODE)
    traffic_mode = config.get(CONF_TRAFFIC_MODE)
    route_mode = config.get(CONF_ROUTE_MODE)
    name = config.get(CONF_NAME)
    units = config.get(CONF_UNIT_SYSTEM, hass.config.units.name)

    here_data = HERETravelTimeData(
        None, None, app_id, app_code, travel_mode, traffic_mode, route_mode, units
    )

    sensor = HERETravelTimeSensor(hass, name, origin, destination, here_data)

    hass.data[DATA_KEY].append(sensor)

    async_add_entities([sensor], True)


class HERETravelTimeSensor(Entity):
    """Representation of a HERE travel time sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        origin: str,
        destination: str,
        here_data: "HERETravelTimeData",
    ) -> None:
        """Initialize the sensor."""
        self._hass = hass
        self._name = name
        self._here_data = here_data
        self._unit_of_measurement = UNIT_OF_MEASUREMENT
        self._origin_entity_id = None
        self._destination_entity_id = None

        # Check if location is a trackable entity
        if origin.split(".", 1)[0] in TRACKABLE_DOMAINS:
            self._origin_entity_id = origin
        else:
            self._here_data.origin = origin

        if destination.split(".", 1)[0] in TRACKABLE_DOMAINS:
            self._destination_entity_id = destination
        else:
            self._here_data.destination = destination

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
    def name(self) -> str:
        """Get the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(
        self
    ) -> Optional[Dict[str, Union[None, float, str, bool]]]:
        """Return the state attributes."""
        if self._here_data.base_time is None:
            return None

        res = {}
        res[ATTR_ATTRIBUTION] = self._here_data.attribution
        res[ATTR_DURATION] = self._here_data.base_time / 60
        res[ATTR_DISTANCE] = self._here_data.distance
        res[ATTR_ROUTE] = self._here_data.route
        res[CONF_UNIT_SYSTEM] = self._here_data.units
        res[ATTR_DURATION_IN_TRAFFIC] = self._here_data.traffic_time / 60
        res[ATTR_ORIGIN] = self._here_data.origin
        res[ATTR_DESTINATION] = self._here_data.destination
        res[ATTR_ORIGIN_NAME] = self._here_data.origin_name
        res[ATTR_DESTINATION_NAME] = self._here_data.destination_name
        res[CONF_MODE] = self._here_data.travel_mode
        res[CONF_TRAFFIC_MODE] = self._here_data.traffic_mode
        return res

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

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

    async def async_update(self) -> None:
        """Update Sensor Information."""
        # Convert device_trackers to HERE friendly location
        if self._origin_entity_id is not None:
            self._here_data.origin = await self._get_location_from_entity(
                self._origin_entity_id
            )

        if self._destination_entity_id is not None:
            self._here_data.destination = await self._get_location_from_entity(
                self._destination_entity_id
            )

        await self._hass.async_add_executor_job(self._here_data.update)

    async def _get_location_from_entity(self, entity_id: str) -> Optional[str]:
        """Get the location from the entity state or attributes."""
        entity = self._hass.states.get(entity_id)

        if entity is None:
            _LOGGER.error("Unable to find entity %s", entity_id)
            return None

        # Check if the entity has location attributes
        if location.has_location(entity):
            return self._get_location_from_attributes(entity)

        # Check if device is in a zone
        zone_entity = self._hass.states.get("zone.{}".format(entity.state))
        if location.has_location(zone_entity):
            _LOGGER.debug(
                "%s is in %s, getting zone location", entity_id, zone_entity.entity_id
            )
            return self._get_location_from_attributes(zone_entity)

        # If zone was not found in state then use the state as the location
        if entity_id.startswith("sensor."):
            return entity.state

    @staticmethod
    def _get_location_from_attributes(entity: State) -> str:
        """Get the lat/long string from an entities attributes."""
        attr = entity.attributes
        return "{},{}".format(attr.get(ATTR_LATITUDE), attr.get(ATTR_LONGITUDE))


class HERETravelTimeData:
    """HERETravelTime data object."""

    def __init__(
        self,
        origin: None,
        destination: None,
        app_id: str,
        app_code: str,
        travel_mode: str,
        traffic_mode: bool,
        route_mode: str,
        units: str,
    ) -> None:
        """Initialize herepy."""
        self.origin = origin
        self.destination = destination
        self.travel_mode = travel_mode
        self.traffic_mode = traffic_mode
        self.route_mode = route_mode
        self.attribution = None
        self.traffic_time = None
        self.distance = None
        self.route = None
        self.base_time = None
        self.origin_name = None
        self.destination_name = None
        self.units = units
        self._client = herepy.RoutingApi(app_id, app_code)

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

            _LOGGER.debug(
                "Requesting route for origin: %s, destination: %s, route_mode: %s, mode: %s, traffic_mode: %s",
                origin,
                destination,
                self.route_mode,
                self.travel_mode,
                traffic_mode,
            )
            response = self._client.car_route(
                origin, destination, [self.route_mode, self.travel_mode, traffic_mode]
            )
            if isinstance(response, herepy.error.HEREError):
                # Better error message for cryptic no route error codes
                if any(error in response.message for error in NO_ROUTE_ERRORS):
                    _LOGGER.error(NO_ROUTE_ERROR_MESSAGE)
                else:
                    _LOGGER.error("API returned error %s", response.message)
                return

            # pylint: disable=no-member
            route = response.response["route"]
            summary = route[0]["summary"]
            waypoint = route[0]["waypoint"]
            maneuver = route[0]["leg"][0]["maneuver"]

            self.attribution = None
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
            if self.travel_mode in TRAVEL_MODES_VEHICLE:
                # Get Route for Car and Truck
                self.route = self._get_route_from_vehicle_maneuver(maneuver)
            elif self.travel_mode in TRAVEL_MODES_PUBLIC:
                # Get Route for Public Transport
                public_transport_line = route[0]["publicTransportLine"]
                self.route = self._get_route_from_public_transport_line(
                    public_transport_line
                )
            elif self.travel_mode in TRAVEL_MODES_NON_VEHICLE:
                # Get Route for Pedestrian and Biyclce
                self.route = self._get_route_from_non_vehicle_maneuver(maneuver)
            self.origin_name = waypoint[0]["mappedRoadName"]
            self.destination_name = waypoint[1]["mappedRoadName"]

    @staticmethod
    def _get_route_from_non_vehicle_maneuver(maneuver: str) -> str:
        """Extract a Waze-like route from the maneuver instructions."""
        road_names: List[str] = []

        for step in maneuver:
            instruction = step["instruction"]
            try:
                road_name = instruction.split('<span class="next-street">')[1].split(
                    "</span>"
                )[0]
                road_name = road_name.replace("(", "").replace(")", "")

                # Only add if it does not repeat
                if not road_names or road_names[-1] != road_name:
                    road_names.append(road_name)
            except IndexError:
                pass  # No street name found in this maneuver step
        route = "; ".join(list(map(str, road_names)))
        return route

    @staticmethod
    def _get_route_from_public_transport_line(
        public_transport_line_segment: str
    ) -> str:
        """Extract Waze-like route info from the public transport lines."""
        lines: List[str] = []
        for line_info in public_transport_line_segment:
            lines.append(line_info["lineName"] + " - " + line_info["destination"])

        route = "; ".join(list(map(str, lines)))
        return route

    @staticmethod
    def _get_route_from_vehicle_maneuver(maneuver: str) -> str:
        """Extract a Waze-like route from the maneuver instructions."""
        road_names: List[str] = []

        for step in maneuver:
            instruction = step["instruction"]
            try:
                road_number = instruction.split('<span class="number">')[1].split(
                    "</span>"
                )[0]
                road_name = road_number.replace("(", "").replace(")", "")

                try:
                    street_name = instruction.split('<span class="next-street">')[
                        1
                    ].split("</span>")[0]
                    street_name = street_name.replace("(", "").replace(")", "")

                    road_name += " - " + street_name
                except IndexError:
                    pass  # No street name found in this maneuver step

                # Only add if it does not repeat
                if not road_names or road_names[-1] != road_name:
                    road_names.append(road_name)
            except IndexError:
                pass  # No road number found in this maneuver step

        route = "; ".join(list(map(str, road_names)))
        return route
