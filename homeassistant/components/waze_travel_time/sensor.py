"""Support for Waze travel time sensor."""
from datetime import timedelta
import logging
import re

import WazeRouteCalculator
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_NAME,
    CONF_REGION,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
    EVENT_HOMEASSISTANT_START,
    TIME_MINUTES,
)
from homeassistant.helpers import location
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_DESTINATION = "destination"
ATTR_DURATION = "duration"
ATTR_DISTANCE = "distance"
ATTR_ORIGIN = "origin"
ATTR_ROUTE = "route"

ATTRIBUTION = "Powered by Waze"

CONF_DESTINATION = "destination"
CONF_ORIGIN = "origin"
CONF_INCL_FILTER = "incl_filter"
CONF_EXCL_FILTER = "excl_filter"
CONF_REALTIME = "realtime"
CONF_UNITS = "units"
CONF_VEHICLE_TYPE = "vehicle_type"
CONF_AVOID_TOLL_ROADS = "avoid_toll_roads"
CONF_AVOID_SUBSCRIPTION_ROADS = "avoid_subscription_roads"
CONF_AVOID_FERRIES = "avoid_ferries"

DEFAULT_NAME = "Waze Travel Time"
DEFAULT_REALTIME = True
DEFAULT_VEHICLE_TYPE = "car"
DEFAULT_AVOID_TOLL_ROADS = False
DEFAULT_AVOID_SUBSCRIPTION_ROADS = False
DEFAULT_AVOID_FERRIES = False

ICON = "mdi:car"

UNITS = [CONF_UNIT_SYSTEM_METRIC, CONF_UNIT_SYSTEM_IMPERIAL]

REGIONS = ["US", "NA", "EU", "IL", "AU"]
VEHICLE_TYPES = ["car", "taxi", "motorcycle"]

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ORIGIN): cv.string,
        vol.Required(CONF_DESTINATION): cv.string,
        vol.Required(CONF_REGION): vol.In(REGIONS),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_INCL_FILTER): cv.string,
        vol.Optional(CONF_EXCL_FILTER): cv.string,
        vol.Optional(CONF_REALTIME, default=DEFAULT_REALTIME): cv.boolean,
        vol.Optional(CONF_VEHICLE_TYPE, default=DEFAULT_VEHICLE_TYPE): vol.In(
            VEHICLE_TYPES
        ),
        vol.Optional(CONF_UNITS): vol.In(UNITS),
        vol.Optional(
            CONF_AVOID_TOLL_ROADS, default=DEFAULT_AVOID_TOLL_ROADS
        ): cv.boolean,
        vol.Optional(
            CONF_AVOID_SUBSCRIPTION_ROADS, default=DEFAULT_AVOID_SUBSCRIPTION_ROADS
        ): cv.boolean,
        vol.Optional(CONF_AVOID_FERRIES, default=DEFAULT_AVOID_FERRIES): cv.boolean,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Waze travel time sensor platform."""
    destination = config.get(CONF_DESTINATION)
    name = config.get(CONF_NAME)
    origin = config.get(CONF_ORIGIN)
    region = config.get(CONF_REGION)
    incl_filter = config.get(CONF_INCL_FILTER)
    excl_filter = config.get(CONF_EXCL_FILTER)
    realtime = config.get(CONF_REALTIME)
    vehicle_type = config.get(CONF_VEHICLE_TYPE)
    avoid_toll_roads = config.get(CONF_AVOID_TOLL_ROADS)
    avoid_subscription_roads = config.get(CONF_AVOID_SUBSCRIPTION_ROADS)
    avoid_ferries = config.get(CONF_AVOID_FERRIES)
    units = config.get(CONF_UNITS, hass.config.units.name)

    data = WazeTravelTimeData(
        None,
        None,
        region,
        incl_filter,
        excl_filter,
        realtime,
        units,
        vehicle_type,
        avoid_toll_roads,
        avoid_subscription_roads,
        avoid_ferries,
    )

    sensor = WazeTravelTime(name, origin, destination, data)

    add_entities([sensor])

    # Wait until start event is sent to load this component.
    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, lambda _: sensor.update())


def _get_location_from_attributes(state):
    """Get the lat/long string from an states attributes."""
    attr = state.attributes
    return "{},{}".format(attr.get(ATTR_LATITUDE), attr.get(ATTR_LONGITUDE))


class WazeTravelTime(SensorEntity):
    """Representation of a Waze travel time sensor."""

    def __init__(self, name, origin, destination, waze_data):
        """Initialize the Waze travel time sensor."""
        self._name = name
        self._waze_data = waze_data
        self._state = None
        self._origin_entity_id = None
        self._destination_entity_id = None

        # Attempt to find entity_id without finding address with period.
        pattern = "(?<![a-zA-Z0-9 ])[a-z_]+[.][a-zA-Z0-9_]+"

        if re.fullmatch(pattern, origin):
            _LOGGER.debug("Found origin source entity %s", origin)
            self._origin_entity_id = origin
        else:
            self._waze_data.origin = origin

        if re.fullmatch(pattern, destination):
            _LOGGER.debug("Found destination source entity %s", destination)
            self._destination_entity_id = destination
        else:
            self._waze_data.destination = destination

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._waze_data.duration is not None:
            return round(self._waze_data.duration)

        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TIME_MINUTES

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the last update."""
        if self._waze_data.duration is None:
            return None

        res = {ATTR_ATTRIBUTION: ATTRIBUTION}
        res[ATTR_DURATION] = self._waze_data.duration
        res[ATTR_DISTANCE] = self._waze_data.distance
        res[ATTR_ROUTE] = self._waze_data.route
        res[ATTR_ORIGIN] = self._waze_data.origin
        res[ATTR_DESTINATION] = self._waze_data.destination
        return res

    def _get_location_from_entity(self, entity_id):
        """Get the location from the entity_id."""
        state = self.hass.states.get(entity_id)

        if state is None:
            _LOGGER.error("Unable to find entity %s", entity_id)
            return None

        # Check if the entity has location attributes.
        if location.has_location(state):
            _LOGGER.debug("Getting %s location", entity_id)
            return _get_location_from_attributes(state)

        # Check if device is inside a zone.
        zone_state = self.hass.states.get(f"zone.{state.state}")
        if location.has_location(zone_state):
            _LOGGER.debug(
                "%s is in %s, getting zone location", entity_id, zone_state.entity_id
            )
            return _get_location_from_attributes(zone_state)

        # If zone was not found in state then use the state as the location.
        if entity_id.startswith("sensor."):
            return state.state

        # When everything fails just return nothing.
        return None

    def _resolve_zone(self, friendly_name):
        """Get a lat/long from a zones friendly_name."""
        states = self.hass.states.all()
        for state in states:
            if state.domain == "zone" and state.name == friendly_name:
                return _get_location_from_attributes(state)

        return friendly_name

    def update(self):
        """Fetch new state data for the sensor."""
        _LOGGER.debug("Fetching Route for %s", self._name)
        # Get origin latitude and longitude from entity_id.
        if self._origin_entity_id is not None:
            self._waze_data.origin = self._get_location_from_entity(
                self._origin_entity_id
            )

        # Get destination latitude and longitude from entity_id.
        if self._destination_entity_id is not None:
            self._waze_data.destination = self._get_location_from_entity(
                self._destination_entity_id
            )

        # Get origin from zone name.
        self._waze_data.origin = self._resolve_zone(self._waze_data.origin)

        # Get destination from zone name.
        self._waze_data.destination = self._resolve_zone(self._waze_data.destination)

        self._waze_data.update()


class WazeTravelTimeData:
    """WazeTravelTime Data object."""

    def __init__(
        self,
        origin,
        destination,
        region,
        include,
        exclude,
        realtime,
        units,
        vehicle_type,
        avoid_toll_roads,
        avoid_subscription_roads,
        avoid_ferries,
    ):
        """Set up WazeRouteCalculator."""

        self._calc = WazeRouteCalculator

        self.origin = origin
        self.destination = destination
        self.region = region
        self.include = include
        self.exclude = exclude
        self.realtime = realtime
        self.units = units
        self.duration = None
        self.distance = None
        self.route = None
        self.avoid_toll_roads = avoid_toll_roads
        self.avoid_subscription_roads = avoid_subscription_roads
        self.avoid_ferries = avoid_ferries

        # Currently WazeRouteCalc only supports PRIVATE, TAXI, MOTORCYCLE.
        if vehicle_type.upper() == "CAR":
            # Empty means PRIVATE for waze which translates to car.
            self.vehicle_type = ""
        else:
            self.vehicle_type = vehicle_type.upper()

    def update(self):
        """Update WazeRouteCalculator Sensor."""
        if self.origin is not None and self.destination is not None:
            try:
                params = self._calc.WazeRouteCalculator(
                    self.origin,
                    self.destination,
                    self.region,
                    self.vehicle_type,
                    self.avoid_toll_roads,
                    self.avoid_subscription_roads,
                    self.avoid_ferries,
                )
                routes = params.calc_all_routes_info(real_time=self.realtime)

                if self.include is not None:
                    routes = {
                        k: v
                        for k, v in routes.items()
                        if self.include.lower() in k.lower()
                    }

                if self.exclude is not None:
                    routes = {
                        k: v
                        for k, v in routes.items()
                        if self.exclude.lower() not in k.lower()
                    }

                route = list(routes)[0]

                self.duration, distance = routes[route]

                if self.units == CONF_UNIT_SYSTEM_IMPERIAL:
                    # Convert to miles.
                    self.distance = distance / 1.609
                else:
                    self.distance = distance

                self.route = route
            except self._calc.WRCError as exp:
                _LOGGER.warning("Error on retrieving data: %s", exp)
                return
            except KeyError:
                _LOGGER.error("Error retrieving data from server")
                return
