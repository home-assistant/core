"""
Support for information about the German trans system.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.deutsche_bahn/
"""
import logging
from datetime import timedelta, datetime
from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['schiene==0.15']
ICON = 'mdi:train'

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the Deutsche Bahn Sensor."""
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
    """Implementation of a Deutsche Bahn sensor."""

    def __init__(self, start, goal):
        """Initialize the sensor."""
        self._name = start + ' to ' + goal
        self.data = SchieneData(start, goal)
        self.update()

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
    def state_attributes(self):
        """Return the state attributes."""
        return self.data.connections[0]

    def update(self):
        """Get the latest delay from bahn.de and updates the state."""
        self.data.update()
        self._state = self.data.connections[0].get('departure', 'Unknown')
        if self.data.connections[0]['delay'] != 0:
            self._state += " + {}".format(
                self.data.connections[0]['delay']
            )


# pylint: disable=too-few-public-methods
class SchieneData(object):
    """Pull data from the bahn.de web page."""

    def __init__(self, start, goal):
        """Initialize the sensor."""
        import schiene
        self.start = start
        self.goal = goal
        self.schiene = schiene.Schiene()
        self.connections = [{}]

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update the connection data."""
        self.connections = self.schiene.connections(self.start,
                                                    self.goal,
                                                    datetime.now())
        for con in self.connections:
            # Details info is not useful.
            # Having a more consistent interface simplifies
            # usage of Template sensors later on
            if 'details' in con:
                con.pop('details')
                delay = con.get('delay',
                                {'delay_departure': 0,
                                 'delay_arrival': 0})
                # IMHO only delay_departure is usefull
                con['delay'] = delay['delay_departure']
                con['ontime'] = con.get('ontime', False)
