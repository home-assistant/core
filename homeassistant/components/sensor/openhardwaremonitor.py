"""
Support for Open Hardware Monitor Sensor Platform.
"""

from threading import Timer
from datetime import timedelta
import logging
import json

import urllib.request
import voluptuous as vol

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
    # update_json(config, add_devices)

    data = OpenHardwareMonitorData(config)
    add_devices(data.devices)


class OpenHardwareMonitorDevice(Entity):
    """Device used to display information from OpenHardwareMonitor."""

    def __init__(self, data, name, path, obj, attributes):
        """Initialize a OpenHardwareMonitor sensor."""
        self._name = name
        self._data = data

        self._path = path
        self._obj = obj
        self._attributes = attributes

        self._state = None
        self._min = None
        self._max = None

        parts = obj[OHM_VALUE].split(' ')
        self._state = parts[0]
        self._unit_of_measurement = parts[1]
        self._min = self._obj[OHM_MIN].split(' ')[0]
        self._max = self._obj[OHM_MAX].split(' ')[0]

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
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes of the sun."""
        result = self._attributes.copy()
        result.update({
            STATE_MIN_VALUE: self._min,
            STATE_MAX_VALUE: self._max
        })
        return result

    def update(self):
        """Update the device from a new JSON object."""
        self._data.update()
        self._obj = self._data.update_object(self._path)

        self._state = self._obj[OHM_VALUE].split(' ')[0]
        self._min = self._obj[OHM_MIN].split(' ')[0]
        self._max = self._obj[OHM_MAX].split(' ')[0]


class OpenHardwareMonitorData(object):
    """Class used to pull data from OHM and create sensors."""

    def __init__(self, config):
        """Initialize the Open Hardware Monitor data-handler."""
        self._data = None
        self._config = config
        self.devices = []
        self.initialize()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Hit by the timer with the configured interval."""
        if self._data is None:
            self.initialize()
        else:
            self.refresh()

    def refresh(self):
        """Download and parse JSON from OHM."""
        host = self._config.get(CONF_HOST)
        port = self._config.get(CONF_PORT)
        data_url = "http://%s:%d/data.json" % (host, port)
        _LOGGER.info("Download from %s", data_url)

        try:
            with urllib.request.urlopen(data_url) as url:
                self._data = json.loads(url.read().decode())
        except urllib.error.URLError:
            _LOGGER.error("URLError: Is OpenHardwareMonitor running?")
        except ConnectionRefusedError:
            _LOGGER.error(
                "Connection refused, is OpenHardwareMonitor running?")

    def schedule_retry(self):
        """Schedule a retry in 30 seconds."""
        _LOGGER.info("Retrying in 30 seconds")
        timer = Timer(30, self.initialize)
        timer.start()

    def initialize(self):
        """Initial parsing of the sensors and adding of deviced."""
        self.refresh()

        if self._data is None:
            self.schedule_retry()
            return

        computer_count = len(self._data[OHM_CHILDREN])
        _LOGGER.info("Detected %d PC(s)", computer_count)

        if computer_count > 0:
            for computer_index in range(0, computer_count):
                computer = self._data[OHM_CHILDREN][computer_index]
                computer_name = computer[OHM_NAME]

                devices = computer[OHM_CHILDREN]
                for device_index in range(0, len(devices)):
                    device = devices[device_index]
                    device_name = device[OHM_NAME]

                    specs = device[OHM_CHILDREN]
                    for spec_index in range(0, len(specs)):
                        spec = specs[spec_index]
                        spec_name = spec[OHM_NAME]

                        values = spec[OHM_CHILDREN]
                        for value_index in range(0, len(values)):
                            value = values[value_index]
                            value_name = value[OHM_NAME]

                            path = []
                            path.append(computer_index)
                            path.append(device_index)
                            path.append(spec_index)
                            path.append(value_index)

                            attributes = {
                                "computer_name": computer_name,
                                "device_name": device_name,
                                "spec_name": spec_name,
                                "value_name": value_name
                            }

                            dev = OpenHardwareMonitorDevice(
                                self,
                                "%s_%s_%s_%s" % (
                                    computer_name,
                                    device_name,
                                    spec_name,
                                    value_name),
                                path, value, attributes)

                            self.devices.append(dev)

    def update_object(self, path):
        """Get the object by specified path."""
        array = self._data[OHM_CHILDREN]

        for path_index in range(0, len(path)):
            path_number = path[path_index]

            if path_index == len(path) - 1:
                return array[path_number]
            else:
                array = array[path_number][OHM_CHILDREN]
