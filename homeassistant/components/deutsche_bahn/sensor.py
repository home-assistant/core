"""Support for information about the German train system."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_DESTINATION = 'to'
CONF_START = 'from'
CONF_ONLY_DIRECT = 'only_direct'
DEFAULT_ONLY_DIRECT = False

ICON = 'mdi:train'

SCAN_INTERVAL = timedelta(minutes=2)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DESTINATION): cv.string,
    vol.Required(CONF_START): cv.string,
    vol.Optional(CONF_ONLY_DIRECT, default=DEFAULT_ONLY_DIRECT): cv.boolean,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Deutsche Bahn Sensor."""
    start = config.get(CONF_START)
    destination = config.get(CONF_DESTINATION)
    only_direct = config.get(CONF_ONLY_DIRECT)

    add_entities([DeutscheBahnSensor(start, destination, only_direct)], True)


class DeutscheBahnSensor(Entity):
    """Implementation of a Deutsche Bahn sensor."""

    def __init__(self, start, goal, only_direct):
        """Initialize the sensor."""
        self._name = '{} to {}'.format(start, goal)
        self.data = SchieneData(start, goal, only_direct)
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the frontend."""
        return ICON

    @property
    def state(self):
        """Return the departure time of the next train."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        connections = self.data.connections[0]
        if len(self.data.connections) > 1:
            connections['next'] = self.data.connections[1]['departure']
        if len(self.data.connections) > 2:
            connections['next_on'] = self.data.connections[2]['departure']
        return connections

    def update(self):
        """Get the latest delay from bahn.de and updates the state."""
        self.data.update()
        self._state = self.data.connections[0].get('departure', 'Unknown')
        if self.data.connections[0].get('delay', 0) != 0:
            self._state += " + {}".format(self.data.connections[0]['delay'])


class SchieneData:
    """Pull data from the bahn.de web page."""

    def __init__(self, start, goal, only_direct):
        """Initialize the sensor."""
        import schiene

        self.start = start
        self.goal = goal
        self.only_direct = only_direct
        self.schiene = schiene.Schiene()
        self.connections = [{}]

    def update(self):
        """Update the connection data."""
        self.connections = self.schiene.connections(
            self.start, self.goal, dt_util.as_local(dt_util.utcnow()),
            self.only_direct)

        if not self.connections:
            self.connections = [{}]

        for con in self.connections:
            # Detail info is not useful. Having a more consistent interface
            # simplifies usage of template sensors.
            if 'details' in con:
                con.pop('details')
                delay = con.get('delay', {'delay_departure': 0,
                                          'delay_arrival': 0})
                con['delay'] = delay['delay_departure']
                con['delay_arrival'] = delay['delay_arrival']
                con['ontime'] = con.get('ontime', False)
