"""
Support for information about the German train system.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.deutsche_bahn/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['schiene==0.20']

_LOGGER = logging.getLogger(__name__)

CONF_DESTINATION = 'to'
CONF_START = 'from'

ICON = 'mdi:train'

SCAN_INTERVAL = timedelta(minutes=2)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DESTINATION): cv.string,
    vol.Required(CONF_START): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Deutsche Bahn Sensor."""
    start = config.get(CONF_START)
    destination = config.get(CONF_DESTINATION)

    add_devices([DeutscheBahnSensor(start, destination)], True)


class DeutscheBahnSensor(Entity):
    """Implementation of a Deutsche Bahn sensor."""

    def __init__(self, start, goal):
        """Initialize the sensor."""
        self._name = '{} to {}'.format(start, goal)
        self.data = SchieneData(start, goal)
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
        connections['next'] = self.data.connections[1]['departure']
        connections['next_on'] = self.data.connections[2]['departure']
        return connections

    def update(self):
        """Get the latest delay from bahn.de and updates the state."""
        self.data.update()
        self._state = self.data.connections[0].get('departure', 'Unknown')
        if self.data.connections[0]['delay'] != 0:
            self._state += " + {}".format(self.data.connections[0]['delay'])


class SchieneData(object):
    """Pull data from the bahn.de web page."""

    def __init__(self, start, goal):
        """Initialize the sensor."""
        import schiene

        self.start = start
        self.goal = goal
        self.schiene = schiene.Schiene()
        self.connections = [{}]

    def update(self):
        """Update the connection data."""
        self.connections = self.schiene.connections(
            self.start, self.goal, dt_util.as_local(dt_util.utcnow()))

        for con in self.connections:
            # Detail info is not useful. Having a more consistent interface
            # simplifies usage of template sensors.
            if 'details' in con:
                con.pop('details')
                delay = con.get('delay', {'delay_departure': 0,
                                          'delay_arrival': 0})
                # IMHO only delay_departure is useful
                con['delay'] = delay['delay_departure']
                con['ontime'] = con.get('ontime', False)
