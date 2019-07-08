"""Support for HERE travel time sensors."""
from datetime import datetime, timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_LATITUDE, ATTR_LONGITUDE, CONF_MODE, CONF_NAME,
    CONF_UNIT_SYSTEM, CONF_UNIT_SYSTEM_METRIC, CONF_UNIT_SYSTEM_IMPERIAL,
    EVENT_HOMEASSISTANT_START)
from homeassistant.helpers import location
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_DESTINATION = 'destination'
CONF_ORIGIN = 'origin'
CONF_APP_ID = 'app_id'
CONF_APP_CODE = 'app_code'
CONF_TRAFFIC_MODE = 'traffic_mode'
CONF_ROUTE_MODE = 'route_mode'

DEFAULT_NAME = "HERE Travel Time"

TRAVEL_MODE_CAR = 'car'
TRAVEL_MODE_PEDESTRIAN = 'pedestrian'
TRAVEL_MODE_PUBLIC = 'publicTransport'
TRAVEL_MODE_TRUCK = 'truck'
TRAVEL_MODE = [
    TRAVEL_MODE_CAR,
    TRAVEL_MODE_PEDESTRIAN,
    TRAVEL_MODE_PUBLIC,
    TRAVEL_MODE_TRUCK,
]
TRAFFIC_MODE_ENABLED = "traffic:enabled"
TRAFFIC_MODE_DISABLED = "traffic:disabled"

ROUTE_MODE_FASTEST = 'fastest'
ROUTE_MODE_SHORTEST = 'shortest'
ROUTE_MODE = [ROUTE_MODE_FASTEST, ROUTE_MODE_SHORTEST]

ICON_CAR = 'mdi:car'
ICON_PEDESTRIAN = 'mdi:walk'
ICON_PUBLIC = 'mdi:bus'
ICON_TRUCK = 'mdi:truck'

UNITS = [CONF_UNIT_SYSTEM_METRIC, CONF_UNIT_SYSTEM_IMPERIAL]

ATTR_DURATION = 'duration'
ATTR_DISTANCE = 'distance'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_APP_ID): cv.string,
        vol.Required(CONF_APP_CODE): cv.string,
        vol.Required(CONF_DESTINATION): cv.string,
        vol.Required(CONF_ORIGIN): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_MODE, default=TRAVEL_MODE_CAR): vol.In(TRAVEL_MODE),
        vol.Optional(
            CONF_ROUTE_MODE, default=ROUTE_MODE_FASTEST
        ): vol.In(ROUTE_MODE),
        vol.Optional(CONF_TRAFFIC_MODE, default=False): cv.boolean,
        vol.Optional(CONF_UNIT_SYSTEM): vol.In(UNITS),
    }
)

TRACKABLE_DOMAINS = ['device_tracker', 'sensor', 'zone', 'person']
DATA_KEY = 'here_travel_time'

NO_ROUTE_ERROR_MESSAGE = "HERE could not find a route based on the input"


def convert_time_to_utc(timestr):
    """Take a string like 08:00:00 and convert it to a unix timestamp."""
    combined = datetime.combine(
        dt_util.start_of_local_day(), dt_util.parse_time(timestr)
    )
    if combined < datetime.now():
        combined = combined + timedelta(days=1)
    return dt_util.as_timestamp(combined)


def setup_platform(hass, config, add_entities_callback, discovery_info=None):
    """Set up the HERE travel time platform."""
    def run_setup(event):
        """
        Delay the setup until Home Assistant is fully initialized.

        This allows any entities to be created already
        """
        hass.data.setdefault(DATA_KEY, [])

        app_id = config[CONF_APP_ID]
        app_code = config[CONF_APP_CODE]
        origin = config[CONF_ORIGIN]
        destination = config[CONF_DESTINATION]

        travel_mode = config.get(CONF_MODE)
        traffic_mode = config.get(CONF_TRAFFIC_MODE)
        route_mode = config.get(CONF_ROUTE_MODE)
        name = config.get(CONF_NAME, DEFAULT_NAME)
        units = config.get(CONF_UNIT_SYSTEM, hass.config.units.name)

        here_data = HERETravelTimeData(None,
                                       None,
                                       app_id,
                                       app_code,
                                       travel_mode,
                                       traffic_mode,
                                       route_mode,
                                       units)

        sensor = HERETravelTimeSensor(hass,
                                      name,
                                      origin,
                                      destination,
                                      here_data)

        hass.data[DATA_KEY].append(sensor)

        add_entities_callback([sensor])

    # Wait until start event is sent to load this component.
    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, run_setup)


class HERETravelTimeSensor(Entity):
    """Representation of a HERE travel time sensor."""

    def __init__(self, hass, name, origin, destination, here_data):
        """Initialize the sensor."""
        self._hass = hass
        self._name = name
        self._here_data = here_data
        self._unit_of_measurement = 'min'

        # Check if location is a trackable entity
        if origin.split('.', 1)[0] in TRACKABLE_DOMAINS:
            self._origin_entity_id = origin
        else:
            self._here_data.origin = origin

        if destination.split('.', 1)[0] in TRACKABLE_DOMAINS:
            self._destination_entity_id = destination
        else:
            self._here_data.destination = destination

        self.update()

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._here_data.duration is not None:
            return round(self._here_data.duration / 60)

        return None

    @property
    def name(self):
        """Get the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._here_data.duration is None:
            return None

        res = {}
        res[ATTR_ATTRIBUTION] = self._here_data.attribution
        res[ATTR_DURATION] = self._here_data.duration
        res[ATTR_DISTANCE] = self._here_data.distance
        res[CONF_UNIT_SYSTEM] = self._here_data.units
        res['duration_without_traffic'] = self._here_data.base_time
        res['origin_name'] = self._here_data.origin_name
        res['destination_name'] = self._here_data.destination_name
        res[CONF_MODE] = self._here_data.travel_mode
        res[CONF_TRAFFIC_MODE] = self._here_data.traffic_mode
        return res

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend depending on travel_mode."""
        if self._here_data.travel_mode == TRAVEL_MODE_PEDESTRIAN:
            return ICON_PEDESTRIAN
        if self._here_data.travel_mode == TRAVEL_MODE_PUBLIC:
            return ICON_PUBLIC
        if self._here_data.travel_mode == TRAVEL_MODE_TRUCK:
            return ICON_TRUCK
        return ICON_CAR

    def update(self):
        """Update Sensor Information."""
        # Convert device_trackers to HERE friendly location
        if hasattr(self, '_origin_entity_id'):
            self._here_data.origin = self._get_location_from_entity(
                self._origin_entity_id
            )

        if hasattr(self, '_destination_entity_id'):
            self._here_data.destination = self._get_location_from_entity(
                self._destination_entity_id
            )

        self._here_data.destination = self._resolve_zone(
            self._here_data.destination)
        self._here_data.origin = self._resolve_zone(
            self._here_data.origin)

        self._here_data.update()

    def _get_location_from_entity(self, entity_id):
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
                "%s is in %s, getting zone location",
                entity_id, zone_entity.entity_id
            )
            return self._get_location_from_attributes(zone_entity)

        # If zone was not found in state then use the state as the location
        if entity_id.startswith("sensor."):
            return entity.state

        # When everything fails just return nothing
        return None

    @staticmethod
    def _get_location_from_attributes(entity):
        """Get the lat/long string from an entities attributes."""
        attr = entity.attributes
        return "{},{}".format(
            attr.get(ATTR_LATITUDE), attr.get(ATTR_LONGITUDE)
        )

    def _resolve_zone(self, friendly_name):
        entities = self._hass.states.all()
        for entity in entities:
            if entity.domain == 'zone' and entity.name == friendly_name:
                return self._get_location_from_attributes(entity)

        return friendly_name


class HERETravelTimeData():
    """HERETravelTime data object."""

    def __init__(self, origin, destination, app_id, app_code, travel_mode,
                 traffic_mode, route_mode, units):
        """Initialize herepy."""
        import herepy
        self.origin = origin
        self.destination = destination
        self.travel_mode = travel_mode
        self.traffic_mode = traffic_mode
        self.route_mode = route_mode
        self.attribution = None
        self.duration = None
        self.distance = None
        self.base_time = None
        self.origin_name = None
        self.destination_name = None
        self.units = units
        self._client = herepy.RoutingApi(app_id, app_code)

    def update(self):
        """Get the latest data from HERE."""
        import herepy
        if self.traffic_mode:
            traffic_mode = TRAFFIC_MODE_ENABLED
        else:
            traffic_mode = TRAFFIC_MODE_DISABLED

        # Convert location to HERE friendly location if not already so
        if not isinstance(self.destination, list):
            self.destination = self.destination.split(',')
        if not isinstance(self.origin, list):
            self.origin = self.origin.split(',')

        if self.destination is not None and self.origin is not None:
            response = self._client.car_route(
                self.origin,
                self.destination,
                [self.travel_mode, self.route_mode, traffic_mode],
            )
            if isinstance(response, herepy.error.HEREError):
                # Better error message for cryptic error code
                if 'NGEO_ERROR_GRAPH_DISCONNECTED' in response.message:
                    _LOGGER.error(NO_ROUTE_ERROR_MESSAGE)
                else:
                    _LOGGER.error("API returned error %s", response.message)
                return

            # pylint: disable=E1101
            route = response.response['route']
            summary = route[0]['summary']
            waypoint = route[0]['waypoint']

            self.attribution = None
            self.base_time = summary['baseTime']
            # Check if trafficTime is in response
            if self.travel_mode in [TRAVEL_MODE_CAR, TRAVEL_MODE_TRUCK]:
                self.duration = summary['trafficTime']
            else:
                self.duration = self.base_time
            distance = summary['distance']
            if self.units == CONF_UNIT_SYSTEM_IMPERIAL:
                # Convert to miles.
                self.distance = distance / 1609.344
            else:
                self.distance = distance
            self.origin_name = waypoint[0]['mappedRoadName']
            self.destination_name = waypoint[1]['mappedRoadName']
