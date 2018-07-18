"""
Support for Modbus Coil sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.modbus/
"""
import logging
import voluptuous as vol

from homeassistant.components import modbus
from homeassistant.const import CONF_NAME, CONF_SLAVE
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.helpers import config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['modbus']

CONF_COIL = 'coil'
CONF_COILS = 'coils'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COILS): [{
        vol.Required(CONF_COIL): cv.positive_int,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_SLAVE): cv.positive_int
    }]
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Modbus binary sensors."""
    sensors = []
    for coil in config.get(CONF_COILS):
        sensors.append(ModbusCoilSensor(
            coil.get(CONF_NAME),
            coil.get(CONF_SLAVE),
            coil.get(CONF_COIL)))
    add_devices(sensors)


class ModbusCoilSensor(BinarySensorDevice):
    """Modbus coil sensor."""

    def __init__(self, name, slave, coil):
        """Initialize the modbus coil sensor."""
        self._name = name
        self._slave = int(slave) if slave else None
        self._coil = int(coil)
        self._value = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._value

    def update(self):
        """Update the state of the sensor."""
        result = modbus.HUB.read_coils(self._slave, self._coil, 1)
        try:
            self._value = result.bits[0]
        except AttributeError:
            _LOGGER.error(
                'No response from modbus slave %s coil %s',
                self._slave,
                self._coil)
