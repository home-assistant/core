"""
Platform for a generic modbus thermostat. This uses a setpoint and process
value within the controller, so both the current temperature register and the
target temperature register need to be configured.

TODO:
 - add support for Farenheit units
 - add support for offsetting register values
 - add support for scaling register values
 - add support for uint and int data types

# Example Modbus Thermostat configuration (required & optional attributes):
climate:
  - platform: modbus
    name: Watlow F4T
    slave: 1
    target_temp_register: 2782 # Control Loop 1 Setpoint
    current_temp_register: 27586 # Universal Input 1 Module 1
    data_type: float
    min_temp: 15
    max_temp: 25

"""
import logging
import struct
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_SLAVE, TEMP_CELSIUS, ATTR_TEMPERATURE)
from homeassistant.components.climate import (
    ClimateDevice, PLATFORM_SCHEMA, SUPPORT_TARGET_TEMPERATURE)

import homeassistant.components.modbus as modbus
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['modbus']

# Parameters not defined by homeassistant.const
CONF_TARGET_TEMP = 'target_temp_register'
CONF_CURRENT_TEMP = 'current_temp_register'
CONF_DATA_TYPE = 'data_type'
CONF_COUNT = 'data_count'
CONF_PRECISION = 'precision'
CONF_MIN_TEMP = 'min_temp'
CONF_MAX_TEMP = 'max_temp'
DATA_TYPE_INT = 'int'
DATA_TYPE_UINT = 'uint'
DATA_TYPE_FLOAT = 'float'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_SLAVE): cv.positive_int,
    vol.Required(CONF_TARGET_TEMP): cv.positive_int,
    vol.Required(CONF_CURRENT_TEMP): cv.positive_int,
    vol.Optional(CONF_DATA_TYPE, default=DATA_TYPE_FLOAT):
        vol.In([DATA_TYPE_INT, DATA_TYPE_UINT, DATA_TYPE_FLOAT]),
    vol.Optional(CONF_COUNT, default=2): cv.positive_int,
    vol.Optional(CONF_PRECISION, default=1): cv.positive_int,
    vol.Optional(CONF_MIN_TEMP): cv.positive_int,
    vol.Optional(CONF_MAX_TEMP): cv.positive_int,
})

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:thermometer"

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Modbus Thermostat Platform."""
    name = config.get(CONF_NAME)
    modbus_slave = config.get(CONF_SLAVE)
    target_temp_register = config.get(CONF_TARGET_TEMP)
    current_temp_register = config.get(CONF_CURRENT_TEMP)
    data_type = config.get(CONF_DATA_TYPE)
    count = config.get(CONF_COUNT)
    precision = config.get(CONF_PRECISION)
    min_temp = config.get(CONF_MIN_TEMP)
    max_temp = config.get(CONF_MAX_TEMP)

    add_devices([ModbusThermostat(name, modbus_slave, target_temp_register,
                                  current_temp_register, data_type, count,
                                  precision, min_temp, max_temp)], True)


class ModbusThermostat(ClimateDevice):
    """Representation of a Modbus Thermostat """

    def __init__(self, name, modbus_slave, target_temp_register,
                 current_temp_register, data_type, count, precision,
                 min_temp, max_temp):
        """Initialize the unit."""
        self._name = name
        self._slave = modbus_slave
        self._target_temperature_register = int(target_temp_register)
        self._current_temperature_register = int(current_temp_register)
        self._target_temperature = None
        self._current_temperature = None
        self._data_type = data_type
        self._count = int(count)
        self._precision = precision
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._structure = '>f'

        data_types = {DATA_TYPE_INT: {1: 'h', 2: 'i', 4: 'q'}}
        data_types[DATA_TYPE_UINT] = {1: 'H', 2: 'I', 4: 'Q'}
        data_types[DATA_TYPE_FLOAT] = {1: 'e', 2: 'f', 4: 'd'}

        self._structure = '>{}'.format(data_types[self._data_type]
                                       [self._count])

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    def update(self):
        """Update Target Temperature"""
        result = modbus.HUB.read_holding_registers(
            self._slave, self._target_temperature_register, self._count)
        byte_string = b''.join(
            [x.to_bytes(2, byteorder='big') for x in result.registers])
        val = struct.unpack(self._structure, byte_string)[0]
        self._target_temperature = format(val, '.{}f'.format(self._precision))

        """Update Current Temperature"""
        result = modbus.HUB.read_holding_registers(
            self._slave, self._current_temperature_register, self._count)
        byte_string = b''.join(
            [x.to_bytes(2, byteorder='big') for x in result.registers])
        val = struct.unpack(self._structure, byte_string)[0]
        self._current_temperature = format(val, '.{}f'.format(self._precision))

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return float(self._current_temperature)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return float(self._target_temperature)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
        byte_string = struct.pack(self._structure,
                                  float(self._target_temperature))
        register_value = struct.unpack('>h', byte_string[0:2])[0]
        modbus.HUB.write_registers(self._slave,
                                   self._target_temperature_register,
                                   [register_value,0])
