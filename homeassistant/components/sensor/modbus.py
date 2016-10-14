"""
Support for Modbus Register sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.modbus/
"""
import logging
import voluptuous as vol

import homeassistant.components.modbus as modbus
from homeassistant.const import (
    CONF_NAME, CONF_OFFSET, CONF_UNIT_OF_MEASUREMENT)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['modbus']

CONF_COUNT = "count"
CONF_PRECISION = "precision"
CONF_REGISTER = "register"
CONF_REGISTERS = "registers"
CONF_SCALE = "scale"
CONF_SLAVE = "slave"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_REGISTERS): [{
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_REGISTER): cv.positive_int,
        vol.Optional(CONF_COUNT, default=1): cv.positive_int,
        vol.Optional(CONF_OFFSET, default=0): vol.Coerce(float),
        vol.Optional(CONF_PRECISION, default=0): cv.positive_int,
        vol.Optional(CONF_SCALE, default=1): vol.Coerce(float),
        vol.Optional(CONF_SLAVE): cv.positive_int,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string
    }]
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Modbus sensors."""
    sensors = []
    for register in config.get(CONF_REGISTERS):
        sensors.append(ModbusRegisterSensor(
            register.get(CONF_NAME),
            register.get(CONF_SLAVE),
            register.get(CONF_REGISTER),
            register.get(CONF_UNIT_OF_MEASUREMENT),
            register.get(CONF_COUNT),
            register.get(CONF_SCALE),
            register.get(CONF_OFFSET),
            register.get(CONF_PRECISION)))
    add_devices(sensors)


class ModbusRegisterSensor(Entity):
    """Modbus resgister sensor."""

    # pylint: disable=too-many-instance-attributes, too-many-arguments
    def __init__(self, name, slave, register, unit_of_measurement, count,
                 scale, offset, precision):
        """Initialize the modbus register sensor."""
        self._name = name
        self._slave = int(slave) if slave else None
        self._register = int(register)
        self._unit_of_measurement = unit_of_measurement
        self._count = int(count)
        self._scale = scale
        self._offset = offset
        self._precision = precision
        self._value = None

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._value

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    def update(self):
        """Update the state of the sensor."""
        result = modbus.HUB.read_holding_registers(
            self._slave,
            self._register,
            self._count)
        val = 0
        if not result:
            _LOGGER.error(
                'No response from modbus slave %s register %s',
                self._slave,
                self._register)
            return
        for i, res in enumerate(result.registers):
            val += res * (2**(i*16))
        self._value = format(
            self._scale * val + self._offset,
            ".{}f".format(self._precision))
