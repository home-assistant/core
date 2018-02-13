"""
Support for Waze travel time sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.waze_travel_time/
"""
import logging
from datetime import timedelta

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['WazeRouteCalculator==0.5']

_LOGGER = logging.getLogger(__name__)

CONF_DESTINATION = 'destination'
CONF_ORIGIN = 'origin'
CONF_OUTPUTS = 'outputs'
CONF_REGION = 'region'
CONF_UPDATE_INTERVAL = 'update_interval'

TIME_UNIT = 'min'  # type: str
DISTANCE_UNIT = 'km'  # type: str

DEFAULT_NAME = 'Waze Travel Time'

OUTPUT_TYPES = {
    'duration':
    ['Duration', TIME_UNIT, 'mdi:timer', 1],
    'distance':
    ['Distance', DISTANCE_UNIT, 'mdi:car', 1],
    'route':
    ['Route', None, 'mdi:car', 0],
}

REGIONS = ['US', 'NA', 'EU', 'IL']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ORIGIN): cv.string,
    vol.Required(CONF_DESTINATION): cv.string,
    vol.Required(CONF_OUTPUTS):
        vol.All(cv.ensure_list, [vol.In(OUTPUT_TYPES)]),
    vol.Optional(CONF_REGION, default='US'):
        vol.All(cv.ensure_list, [vol.In(REGIONS)]),
    vol.Optional(CONF_UPDATE_INTERVAL, default=timedelta(seconds=300)):
        vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the sensor platform."""
    name = config.get(CONF_NAME)
    origin = config.get(CONF_ORIGIN)
    destination = config.get(CONF_DESTINATION)
    region = config.get(CONF_REGION)[0]
    update_interval = config.get(CONF_UPDATE_INTERVAL)

    try:
        waze_data = WazeRouteData(
            origin, destination, region, update_interval
            )
    except requests.exceptions.HTTPError as error:
        _LOGGER.error("Error: %s", error)
        return False

    for output_type in config[CONF_OUTPUTS]:
        add_devices(
            [WazeTravelTime(
                waze_data, output_type, update_interval, name
                )], True
            )


class WazeTravelTime(Entity):
    """Representation of a Sensor."""

    def __init__(self, waze_data, output_type, update_interval, name):
        """Initialize the sensor."""
        self.type = output_type
        self.sensor_name = name
        self._name = OUTPUT_TYPES[output_type][0]
        self._unit_of_measurement = OUTPUT_TYPES[output_type][1]
        self._icon = OUTPUT_TYPES[output_type][2]
        self._resolution = OUTPUT_TYPES[output_type][3]
        self.waze_data = waze_data
        self._state = None
        self.update = Throttle(update_interval)(self.__update)

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.sensor_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    def __update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        try:
            self.waze_data.update()
            if self.type in self.waze_data.data:
                if self.type == 'route':
                    self._state = self.waze_data.data[self.type]
                    _LOGGER.debug(
                        "Retreived route is %s = %s %s",
                        self.type,
                        self._state
                        )
                else:
                    self._state = round(
                        self.waze_data.data[self.type], self._resolution)
                    _LOGGER.debug(
                        "Retreived route is %s = %s %s",
                        self.type,
                        self._state,
                        self._unit_of_measurement
                        )
        except KeyError:
            _LOGGER.error("Error retreiving data from server")


class WazeRouteData(object):
    """Get data from WazeRouteCalculator."""

    def __init__(self, origin, destination, region, update_interval):
        """Initialize the data object."""
        self._origin = origin
        self._destination = destination
        self._region = region
        self.data = {}

        self.update = Throttle(update_interval)(self.__update)

    def _fetch_data(self):
        """Fetch latest data from WazeRouteCalculator."""
        import WazeRouteCalculator
        _LOGGER.debug("Update in progress")
        try:
            params = WazeRouteCalculator.WazeRouteCalculator(
                self._origin, self._destination, self._region, None)
            results = params.calc_all_routes_info()
            best_route = next(iter(results))
            (duration, distance) = results[best_route]
            best_route_str = bytes(best_route, 'ISO-8859-1').decode('UTF-8')
            self.data['duration'] = duration
            self.data['distance'] = distance
            self.data['route'] = best_route_str
        except WazeRouteCalculator.WRCError as exp:
            _LOGGER.error("Error on retreiving data: %s", exp)
            return

    def __update(self):
        """Return the latest collected data from WazeRouteCalculator."""
        self._fetch_data()
