"""Support for Modbus Coil sensors."""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_SLAVE
from homeassistant.helpers import config_validation as cv

from . import CONF_HUB, DEFAULT_HUB, DOMAIN as MODBUS_DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_COIL = 'coil'
CONF_COILS = 'coils'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COILS): [{
        vol.Required(CONF_COIL): cv.positive_int,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
        vol.Optional(CONF_SLAVE): cv.positive_int,
    }]
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Modbus binary sensors."""
    sensors = []
    for coil in config.get(CONF_COILS):
        hub = hass.data[MODBUS_DOMAIN][coil.get(CONF_HUB)]
        sensors.append(ModbusCoilSensor(
            hub, coil.get(CONF_NAME), coil.get(CONF_SLAVE),
            coil.get(CONF_COIL)))

    add_entities(sensors)


class ModbusCoilSensor(BinarySensorDevice):
    """Modbus coil sensor."""

    def __init__(self, hub, name, slave, coil):
        """Initialize the Modbus coil sensor."""
        self._hub = hub
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
        result = self._hub.read_coils(self._slave, self._coil, 1)
        try:
            self._value = result.bits[0]
        except AttributeError:
            _LOGGER.error("No response from hub %s, slave %s, coil %s",
                          self._hub.name, self._slave, self._coil)
