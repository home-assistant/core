"""
Support for Waze travel time sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.waze_travel_time/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_NAME, CONF_REGION, EVENT_HOMEASSISTANT_START,
    ATTR_LATITUDE, ATTR_LONGITUDE)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import location
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['WazeRouteCalculator==0.6']

_LOGGER = logging.getLogger(__name__)

ATTR_DURATION = 'duration'
ATTR_DISTANCE = 'distance'
ATTR_ROUTE = 'route'

CONF_ATTRIBUTION = "Powered by Waze"
CONF_DESTINATION = 'destination'
CONF_ORIGIN = 'origin'
CONF_INCL_FILTER = 'incl_filter'
CONF_EXCL_FILTER = 'excl_filter'
CONF_REALTIME = 'realtime'

DEFAULT_NAME = 'Waze Travel Time'
DEFAULT_REALTIME = True

ICON = 'mdi:car'

REGIONS = ['US', 'NA', 'EU', 'IL', 'AU']

SCAN_INTERVAL = timedelta(minutes=5)

TRACKABLE_DOMAINS = ['device_tracker', 'sensor', 'zone']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ORIGIN): cv.string,
    vol.Required(CONF_DESTINATION): cv.string,
    vol.Required(CONF_REGION): vol.In(REGIONS),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_INCL_FILTER): cv.string,
    vol.Optional(CONF_EXCL_FILTER): cv.string,
    vol.Optional(CONF_REALTIME, default=DEFAULT_REALTIME): cv.boolean,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Waze travel time sensor platform."""
    destination = config.get(CONF_DESTINATION)
    name = config.get(CONF_NAME)
    origin = config.get(CONF_ORIGIN)
    region = config.get(CONF_REGION)
    incl_filter = config.get(CONF_INCL_FILTER)
    excl_filter = config.get(CONF_EXCL_FILTER)
    realtime = config.get(CONF_REALTIME)

    sensor = WazeTravelTime(name, origin, destination, region,
                            incl_filter, excl_filter, realtime)

    add_entities([sensor])

    # Wait until start event is sent to load this component.
    hass.bus.listen_once(
        EVENT_HOMEASSISTANT_START, lambda _: sensor.update())


def _get_location_from_attributes(state):
    """Get the lat/long string from an states attributes."""
    attr = state.attributes
    return '{},{}'.format(attr.get(ATTR_LATITUDE), attr.get(ATTR_LONGITUDE))


class WazeTravelTime(Entity):
    """Representation of a Waze travel time sensor."""

    def __init__(self, name, origin, destination, region,
                 incl_filter, excl_filter, realtime):
        """Initialize the Waze travel time sensor."""
        self._name = name
        self._region = region
        self._incl_filter = incl_filter
        self._excl_filter = excl_filter
        self._realtime = realtime
        self._state = None
        self._origin_entity_id = None
        self._destination_entity_id = None

        if origin.split('.', 1)[0] in TRACKABLE_DOMAINS:
            self._origin_entity_id = origin
        else:
            self._origin = origin

        if destination.split('.', 1)[0] in TRACKABLE_DOMAINS:
            self._destination_entity_id = destination
        else:
            self._destination = destination

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._state is None:
            return None

        if 'duration' in self._state:
            return round(self._state['duration'])
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return 'min'

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes of the last update."""
        if self._state is None:
            return None

        res = {ATTR_ATTRIBUTION: CONF_ATTRIBUTION}
        if 'duration' in self._state:
            res[ATTR_DURATION] = self._state['duration']
        if 'distance' in self._state:
            res[ATTR_DISTANCE] = self._state['distance']
        if 'route' in self._state:
            res[ATTR_ROUTE] = self._state['route']
        return res

    def _get_location_from_entity(self, entity_id):
        """Get the location from the entity_id."""
        state = self.hass.states.get(entity_id)

        if state is None:
            _LOGGER.error("Unable to find entity %s", entity_id)
            return None

        # Check if the entity has location attributes (zone)
        if location.has_location(state):
            return _get_location_from_attributes(state)

        # Check if device is in a zone (device_tracker)
        zone_state = self.hass.states.get('zone.{}'.format(state.state))
        if location.has_location(zone_state):
            _LOGGER.debug(
                "%s is in %s, getting zone location",
                entity_id, zone_state.entity_id
            )
            return _get_location_from_attributes(zone_state)

        # If zone was not found in state then use the state as the location
        if entity_id.startswith('sensor.'):
            return state.state

        # When everything fails just return nothing
        return None

    def _resolve_zone(self, friendly_name):
        """Get a lat/long from a zones friendly_name."""
        states = self.hass.states.all()
        for state in states:
            if state.domain == 'zone' and state.name == friendly_name:
                return _get_location_from_attributes(state)

        return friendly_name

    def update(self):
        """Fetch new state data for the sensor."""
        import WazeRouteCalculator

        if self._origin_entity_id is not None:
            self._origin = self._get_location_from_entity(
                self._origin_entity_id)

        if self._destination_entity_id is not None:
            self._destination = self._get_location_from_entity(
                self._destination_entity_id)

        self._destination = self._resolve_zone(self._destination)
        self._origin = self._resolve_zone(self._origin)

        if self._destination is not None and self._origin is not None:
            try:
                params = WazeRouteCalculator.WazeRouteCalculator(
                    self._origin, self._destination, self._region)
                routes = params.calc_all_routes_info(real_time=self._realtime)

                if self._incl_filter is not None:
                    routes = {k: v for k, v in routes.items() if
                              self._incl_filter.lower() in k.lower()}

                if self._excl_filter is not None:
                    routes = {k: v for k, v in routes.items() if
                              self._excl_filter.lower() not in k.lower()}

                route = sorted(routes, key=(lambda key: routes[key][0]))[0]
                duration, distance = routes[route]
                route = bytes(route, 'ISO-8859-1').decode('UTF-8')
                self._state = {
                    'duration': duration,
                    'distance': distance,
                    'route': route,
                }
            except WazeRouteCalculator.WRCError as exp:
                _LOGGER.error("Error on retrieving data: %s", exp)
                return
            except KeyError:
                _LOGGER.error("Error retrieving data from server")
                return
