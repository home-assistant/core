"""Support for Open Hardware Monitor Sensor Platform."""

from datetime import timedelta
import logging
import requests
import voluptuous as vol

from homeassistant.util.dt import utcnow
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.const import CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

STATE_MIN_VALUE = 'minimal_value'
STATE_MAX_VALUE = 'maximum_value'
STATE_VALUE = 'value'
STATE_OBJECT = 'object'
CONF_INTERVAL = 'interval'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=1)
SCAN_INTERVAL = timedelta(seconds=5)
RETRY_INTERVAL = timedelta(seconds=30)

OHM_VALUE = 'Value'
OHM_MIN = 'Min'
OHM_MAX = 'Max'
OHM_CHILDREN = 'Children'
OHM_NAME = 'Text'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=8085): cv.port
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Open Hardware Monitor platform."""
    data = OpenHardwareMonitorData(config, hass)
    add_devices(data.devices, True)


class OpenHardwareMonitorDevice(Entity):
    """Device used to display information from OpenHardwareMonitor."""

    def __init__(self, data, name, path, unit_of_measurement):
        """Initialize an OpenHardwareMonitor sensor."""
        self._name = name
        self._data = data
        self.path = path
        self.attributes = {}
        self._unit_of_measurement = unit_of_measurement

        self.value = None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the device."""
        return self.value

    @property
    def state_attributes(self):
        """Return the state attributes of the sun."""
        return self.attributes

    def update(self):
        """Update the device from a new JSON object."""
        self._data.update()
        self._data.update_device(self)


class OpenHardwareMonitorData(object):
    """Class used to pull data from OHM and create sensors."""

    def __init__(self, config, hass):
        """Initialize the Open Hardware Monitor data-handler."""
        self._data = None
        self._config = config
        self._hass = hass
        self.devices = []
        self.initialize(utcnow())

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Hit by the timer with the configured interval."""
        if self._data is None:
            self.initialize(utcnow())
        else:
            self.refresh()

    def refresh(self):
        """Download and parse JSON from OHM."""
        data_url = "http://%s:%d/data.json" % (
            self._config.get(CONF_HOST),
            self._config.get(CONF_PORT))

        try:
            response = requests.get(data_url)
            self._data = response.json()
        except requests.exceptions.ConnectionError:
            _LOGGER.error("ConnectionError: Is OpenHardwareMonitor running?")

    def schedule_retry(self):
        """Schedule a retry in 30 seconds."""
        _LOGGER.info("Retrying in 30 seconds")

        async_track_point_in_utc_time(
            self._hass, self.initialize, utcnow() + RETRY_INTERVAL)

    def initialize(self, now):
        """Initial parsing of the sensors and adding of devices."""
        self.refresh()

        if self._data is None:
            self.schedule_retry()
            return

        self.devices = self.parse_children(self._data, [], [], [])

    def parse_children(self, json, devices, path, names):
        """Recursively loop through child objects, finding the values."""
        result = devices.copy()

        if len(json[OHM_CHILDREN]) > 0:
            for child_index in range(0, len(json[OHM_CHILDREN])):
                child_path = path.copy()
                child_path.append(child_index)

                child_names = names.copy()
                if len(path) > 0:
                    child_names.append(json[OHM_NAME])

                obj = json[OHM_CHILDREN][child_index]

                added_devices = self.parse_children(
                    obj, devices, child_path, child_names)

                result = result + added_devices
        else:
            if json[OHM_VALUE].find(' ') > -1:
                unit_of_measurement = json[OHM_VALUE].split(' ')[1]

                child_names = names.copy()
                child_names.append(json[OHM_NAME])

                fullname = '_'.join(child_names).replace(' ', '_')

                dev = OpenHardwareMonitorDevice(
                    self,
                    fullname,
                    path,
                    unit_of_measurement
                )

                result.append(dev)

        return result

    def update_device(self, device):
        """Update device."""
        array = self._data[OHM_CHILDREN]

        attributes = {}
        for path_index in range(0, len(device.path)):
            path_number = device.path[path_index]
            values = array[path_number]

            if path_index == len(device.path) - 1:
                device.value = values[OHM_VALUE].split(' ')[0]
                attributes.update({
                    'name': values[OHM_NAME],
                    STATE_MIN_VALUE: values[OHM_MIN].split(' ')[0],
                    STATE_MAX_VALUE: values[OHM_MAX].split(' ')[0]
                })

                device.attributes = attributes
                return
            else:
                array = array[path_number][OHM_CHILDREN]
                attributes.update({
                    'level_%s' % path_index: values[OHM_NAME]
                })
