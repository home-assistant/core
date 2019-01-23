"""
Sensor to get GTT's timetable for a stop.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.gtt/
"""
import logging
from datetime import timedelta, datetime

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import DEVICE_CLASS_TIMESTAMP
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pygtt==1.1.2']

_LOGGER = logging.getLogger(__name__)

CONF_STOP = 'stop'
CONF_BUS_NAME = 'bus_name'

ICON = 'mdi:train'

SCAN_INTERVAL = timedelta(minutes=2)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STOP): cv.string,
    vol.Optional(CONF_BUS_NAME): cv.string
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Gtt platform."""
    stop = config[CONF_STOP]
    bus_name = config.get(CONF_BUS_NAME)

    add_entities([GttSensor(stop, bus_name)], True)


class GttSensor(Entity):
    """Representation of a Gtt Sensor."""

    def __init__(self, stop, bus_name):
        """Initialize the Gtt sensor."""
        self.data = GttData(stop, bus_name)
        self._state = None
        self._name = 'Stop {}'.format(stop)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_TIMESTAMP

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        attr = {
            'bus_name': self.data.state_bus['bus_name']
        }
        return attr

    def update(self):
        """Update device state."""
        self.data.get_data()
        next_time = get_datetime(self.data.state_bus)
        self._state = next_time.isoformat()


class GttData:
    """Inteface to PyGTT."""

    def __init__(self, stop, bus_name):
        """Initialize the GttData class."""
        from pygtt import PyGTT
        self._pygtt = PyGTT()
        self._stop = stop
        self._bus_name = bus_name
        self.bus_list = {}
        self.state_bus = {}

    def get_data(self):
        """Get the data from the api."""
        self.bus_list = self._pygtt.get_by_stop(self._stop)
        self.bus_list.sort(key=get_datetime)

        if self._bus_name is not None:
            self.state_bus = self.get_bus_by_name()
            return

        self.state_bus = self.bus_list[0]

    def get_bus_by_name(self):
        """Get the bus by name."""
        for bus in self.bus_list:
            if bus['bus_name'] == self._bus_name:
                return bus


def get_datetime(bus):
    """Get the datetime from a bus."""
    bustime = datetime.strptime(bus['time'][0]['run'], "%H:%M")
    now = datetime.now()
    bustime = bustime.replace(year=now.year, month=now.month, day=now.day)
    if bustime < now:
        bustime = bustime + timedelta(days=1)
    return bustime
