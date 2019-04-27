"""Support for Västtrafik public transport."""
from datetime import datetime
from datetime import timedelta
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTR_ACCESSIBILITY = 'accessibility'
ATTR_DIRECTION = 'direction'
ATTR_LINE = 'line'
ATTR_TRACK = 'track'
ATTRIBUTION = "Data provided by Västtrafik"

CONF_DELAY = 'delay'
CONF_DEPARTURES = 'departures'
CONF_FROM = 'from'
CONF_HEADING = 'heading'
CONF_LINES = 'lines'
CONF_KEY = 'key'
CONF_SECRET = 'secret'

DEFAULT_DELAY = 0

ICON = 'mdi:train'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_KEY): cv.string,
    vol.Required(CONF_SECRET): cv.string,
    vol.Optional(CONF_DEPARTURES): [{
        vol.Required(CONF_FROM): cv.string,
        vol.Optional(CONF_DELAY, default=DEFAULT_DELAY): cv.positive_int,
        vol.Optional(CONF_HEADING): cv.string,
        vol.Optional(CONF_LINES, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_NAME): cv.string}]
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the departure sensor."""
    import vasttrafik
    planner = vasttrafik.JournyPlanner(
        config.get(CONF_KEY), config.get(CONF_SECRET))
    sensors = []

    for departure in config.get(CONF_DEPARTURES):
        sensors.append(
            VasttrafikDepartureSensor(
                vasttrafik, planner, departure.get(CONF_NAME),
                departure.get(CONF_FROM), departure.get(CONF_HEADING),
                departure.get(CONF_LINES), departure.get(CONF_DELAY)))
    add_entities(sensors, True)


class VasttrafikDepartureSensor(Entity):
    """Implementation of a Vasttrafik Departure Sensor."""

    def __init__(self, vasttrafik, planner, name, departure, heading,
                 lines, delay):
        """Initialize the sensor."""
        self._vasttrafik = vasttrafik
        self._planner = planner
        self._name = name or departure
        self._departure = planner.location_name(departure)[0]
        self._heading = (planner.location_name(heading)[0]
                         if heading else None)
        self._lines = lines if lines else None
        self._delay = timedelta(minutes=delay)
        self._departureboard = None
        self._state = None
        self._attributes = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the frontend."""
        return ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def state(self):
        """Return the next departure time."""
        return self._state

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the departure board."""
        try:
            self._departureboard = self._planner.departureboard(
                self._departure['id'],
                direction=self._heading['id'] if self._heading else None,
                date=datetime.now()+self._delay)
        except self._vasttrafik.Error:
            _LOGGER.debug("Unable to read departure board, updating token")
            self._planner.update_token()

        if not self._departureboard:
            _LOGGER.debug(
                "No departures from %s heading %s",
                self._departure['name'],
                self._heading['name'] if self._heading else 'ANY')
            self._state = None
            self._attributes = {}
        else:
            for departure in self._departureboard:
                line = departure.get('sname')
                if not self._lines or line in self._lines:
                    if 'rtTime' in self._departureboard[0]:
                        self._state = self._departureboard[0]['rtTime']
                    else:
                        self._state = self._departureboard[0]['time']

                    params = {
                        ATTR_ACCESSIBILITY: departure.get('accessibility'),
                        ATTR_ATTRIBUTION: ATTRIBUTION,
                        ATTR_DIRECTION: departure.get('direction'),
                        ATTR_LINE: departure.get('sname'),
                        ATTR_TRACK: departure.get('track'),
                    }

                    self._attributes = {
                        k: v for k, v in params.items() if v}
                    break
