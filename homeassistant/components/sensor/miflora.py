"""
Support for Xiaomi Mi Flora BLE plant sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.miflora/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_NAME


REQUIREMENTS = ['miflora==0.1.4']

LOGGER = logging.getLogger(__name__)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=900)
CONF_MAC = "mac"
CONF_FORCE_UPDATE = 'force_update'
DEFAULT_NAME = ""

# Sensor types are defined like: Name, units
SENSOR_TYPES = {
    'temperature': ['Temperature', '°C'],
    'light': ['Light intensity', 'lux'],
    'moisture': ['Moisture', '%'],
    'conductivity': ['Conductivity', 'µS/cm'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MAC): cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_FORCE_UPDATE, default=False): cv.boolean,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the MiFlora sensor."""
    from miflora import miflora_poller

    poller = miflora_poller.MiFloraPoller(config.get(CONF_MAC))
    force_update = config.get(CONF_FORCE_UPDATE)

    devs = []
    try:
        for parameter in config[CONF_MONITORED_CONDITIONS]:
            name = SENSOR_TYPES[parameter][0]
            unit = SENSOR_TYPES[parameter][1]

            prefix = config.get(CONF_NAME)

            if prefix == "":
                # If no name is given, retrieve the name from the device
                # this is usually "Flower mate"
                prefix = poller.name()

            if len(prefix) > 0:
                name = prefix + " " + name
            devs.append(MiFloraSensor(poller,
                                      parameter,
                                      name, unit,
                                      force_update))
    except KeyError as err:
        LOGGER.error("Sensor type %s unknown", err)
        return False

    add_devices(devs)

    return True


class MiFloraSensor(Entity):
    """Implementing the MiFlora sensor."""

# pylint: disable=too-many-instance-attributes,too-many-arguments
    def __init__(self, poller, parameter, name, unit, force_update):
        """Initialize the sensor."""
        self.poller = poller
        self.parameter = parameter
        self._unit = unit
        self._name = name
        self._state = None
        self.data = []
        self._force_update = force_update
        # Median is used to filter out outliers. median of 3 will filter
        # single outliers, while  median of 5 will filter double outliers
        # Use median_count = 1 if no filtering is required.
        self.median_count = 3

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

    @property
    def force_update(self):
        """Force update."""
        return self._force_update

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """
        Update current conditions.

        This uses a rolling median over 3 values to filter out outliers.
        """
        try:
            data = self.poller.parameter_value(self.parameter)
        except IOError:
            return

        if data:
            LOGGER.debug("%s = %s", self.name, data)
            self.data.append(data)
        else:
            LOGGER.debug("Did not receive any data for %s", self.name)

        LOGGER.debug("Data collected: %s", self.data)
        if len(self.data) > self.median_count:
            self.data = self.data[1:]

        if len(self.data) == self.median_count:
            median = sorted(self.data)[int((self.median_count - 1) / 2)]
            LOGGER.debug("Median is: %s", median)
            self._state = median
        else:
            LOGGER.debug("Not yet enough data for median calculation")
