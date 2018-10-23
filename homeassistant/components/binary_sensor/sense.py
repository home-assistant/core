"""
Support for monitoring a Sense energy sensor device.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.sense/
"""
import logging
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sense import SENSE_DATA

_LOGGER = logging.getLogger(__name__)

BIN_SENSOR_CLASS = 'power'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Sense sensor."""
    data = hass.data[SENSE_DATA]

    devices = []
    device = config.get(CONF_NAME)
    devices.append(SenseDevice(data, device))

    add_entities(devices)


class SenseDevice(BinarySensorDevice):
    """Implementation of a Sense energy device binary sensor."""

    def __init__(self, data, name):
        """Initialize the sensor."""
        self._name = name
        self._data = data
        self._state = False

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the device class of the binary sensor."""
        return BIN_SENSOR_CLASS

    def update(self):
        """Retrieve latest state."""
        from sense_energy import SenseAPITimeoutException
        try:
            self._data.get_realtime()
        except SenseAPITimeoutException:
            _LOGGER.error("Timeout retrieving data")
            return
        self._state = self._name in self._data.active_devices
