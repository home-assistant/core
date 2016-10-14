"""
Support for CO2 sensor connected to a serial port.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mhz19/
"""
import logging
import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA

REQUIREMENTS = ['pmsensor==0.3']


_LOGGER = logging.getLogger(__name__)

CONF_SERIAL_DEVICE = "serial_device"
DEFAULT_NAME = 'CO2 Sensor'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_SERIAL_DEVICE): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the available CO2 sensors."""
    from pmsensor import co2sensor

    try:
        co2sensor.read_mh_z19(config.get(CONF_SERIAL_DEVICE))
    except OSError as err:
        _LOGGER.error("Could not open serial connection to %s (%s)",
                      config.get(CONF_SERIAL_DEVICE), err)
        return False

    dev = MHZ19Sensor(config.get(CONF_SERIAL_DEVICE), config.get(CONF_NAME))
    add_devices([dev])


class MHZ19Sensor(Entity):
    """Representation of an CO2 sensor."""

    def __init__(self, serial_device, name):
        """Initialize a new PM sensor."""
        self._name = name
        self._state = None
        self._serial = serial_device

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
        """Return the unit of measurement of this entity, if any."""
        return "ppm"

    def update(self):
        """Read from sensor and update the state."""
        from pmsensor import co2sensor

        _LOGGER.debug("Reading data from CO2 sensor")
        try:
            ppm = co2sensor.read_mh_z19(self._serial)
            # values from sensor can only between 0 and 5000
            if (ppm >= 0) & (ppm <= 5000):
                self._state = ppm
        except OSError as err:
            _LOGGER.error("Could not open serial connection to %s (%s)",
                          self._serial, err)
            return

    def should_poll(self):
        """Sensor needs polling."""
        return True
