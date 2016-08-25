"""
Support for Xiaomi Mi Flora BLE plant sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.miflora/
"""
from datetime import timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_NAME


REQUIREMENTS = ['miflora==0.1']

LOGGER = logging.getLogger(__name__)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=900)
CONF_MAC = "mac"
DEFAULT_NAME = ""

# Sensor types are defined like: Name, units
SENSOR_TYPES = {
    'temperature': ['Temperature', '°C'],
    'light': ['Light intensity', 'lux'],
    'moisture': ['Moisture', '%'],
    'fertility': ['Fertility', ''],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MAC): cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the MiFlora sensor."""
    from miflora.miflora_poller import MiFloraPoller
    poller = MiFloraPoller(config.get(CONF_MAC))

    devs = []
    try:
        for parameter in config[CONF_MONITORED_CONDITIONS]:
            name = SENSOR_TYPES[parameter][0]
            unit = SENSOR_TYPES[parameter][1]
            devs.append(MiFloraSensor(poller, parameter, name, unit))
    except KeyError as err:
        _LOGGER.error("Sensor type %s unknown", err)
        return False

    add_devices(devs)

    return True


class MiFloraSensor(Entity):
    """Implementing the MiFlora sensor."""

    def __init__(self, poller, parameter, name, unit, median_count=3):
        """Initialize the sensor."""
        self._poller = poller
        self._parameter = paramater
        self._unit = unit
        self._name = name
        self._unit = unit
        self._state = None
        self._data = []
        self._median_count = median_count

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return self._unit

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update current conditions.

        This uses a rolling median to filter out outliers
        """

        data = self.poller.parameter_value(self._parameter)
        if data:
            LOGGER.debug("%s = %s", self._name, data)
            self._data.append()
        else:
            LOGGER.debug("Did not receive any data for %s", self._name)

        LOGGER.debug("Data collected: %s", self._data)
        if (len(self._data) > self._median_count):
            self._data = self._data[1:]

        if (len(self._data) == self._median_count):
            median = sorted(self.data)[int((self._median_count - 1) / 2)]
            LOGGER.debug("Median is: %s", median)
        else:
            LOGGER.debug("Not yet enough data for median calculation", median)
