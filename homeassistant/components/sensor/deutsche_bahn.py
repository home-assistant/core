'''
homeassistant.components.sensor.bahn
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The deutsche_bahn sensor tells you if your next train is on time, or delayed.

'''

import logging
from datetime import timedelta, datetime
from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['schiene==0.14']

ICON = 'mdi:train'

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Add the Bahn Sensor. """
    start = config.get('from')
    goal = config.get('to')

    if start is None:
        _LOGGER.error('Missing required variable: "from"')
        return False

    if goal is None:
        _LOGGER.error('Missing required variable: "to"')
        return False

    dev = []
    dev.append(DeutscheBahnSensor(start, goal))
    add_devices_callback(dev)


# pylint: disable=too-few-public-methods
class DeutscheBahnSensor(Entity):
    """Implement a DeutscheBahn  sensor
    start:     starting station
    goal:      target station"""
    def __init__(self, start, goal):
        self._name = start + ' to ' + goal
        self.data = SchieneData(start, goal)
        self.update()

    @property
    def name(self):
        """ return the name."""
        return self._name

    @property
    def icon(self):
        """ Icon for the frontend"""
        return ICON

    @property
    def state(self):
        """Return the depature time of the next train"""
        return self._state

    @property
    def state_attributes(self):
        return self.data.connections[0]

    def update(self):
        """ Gets the latest delay from bahn.de and updates the state"""
        self.data.update()
        self._state = self.data.connections[0].get('departure', 'Unknown')
        delay = self.data.connections[0].get('delay',
                                             {'delay_departure': 0,
                                              'delay_arrival': 0})
        if delay['delay_departure'] != 0:
            self._state += " + {}".format(delay['delay_departure'])


# pylint: disable=too-few-public-methods
class SchieneData(object):
    """ Pulls data from the bahn.de web page"""
    def __init__(self, start, goal):
        import schiene
        self.start = start
        self.goal = goal
        self.schiene = schiene.Schiene()
        self.connections = [{}]

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """ update connection data"""
        self.connections = self.schiene.connections(self.start,
                                                    self.goal,
                                                    datetime.now())
        for con in self.connections:
            if 'details' in con:
                con.pop('details')  # details info is not usefull
