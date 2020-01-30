"""Support for Generic Modbus Thermostats."""
import logging
import struct

import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_SLAVE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv

from . import CONF_HUB, DEFAULT_HUB, DOMAIN as MODBUS_DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_TARGET_TEMP = "target_temp_register"
CONF_CURRENT_TEMP = "current_temp_register"
CONF_DATA_TYPE = "data_type"
CONF_COUNT = "data_count"
CONF_PRECISION = "precision"
CONF_SCALE = "scale"
CONF_OFFSET = "offset"
CONF_UNIT = "temperature_unit"
DATA_TYPE_INT = "int"
DATA_TYPE_UINT = "uint"
DATA_TYPE_FLOAT = "float"
CONF_MAX_TEMP = "max_temp"
CONF_MIN_TEMP = "min_temp"
CONF_STEP = "temp_step"
SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE
HVAC_MODES = [HVAC_MODE_AUTO]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_CURRENT_TEMP): cv.positive_int,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_SLAVE): cv.positive_int,
        vol.Required(CONF_TARGET_TEMP): cv.positive_int,
        vol.Optional(CONF_COUNT, default=2): cv.positive_int,
        vol.Optional(CONF_DATA_TYPE, default=DATA_TYPE_FLOAT): vol.In(
            [DATA_TYPE_INT, DATA_TYPE_UINT, DATA_TYPE_FLOAT]
        ),
        vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
        vol.Optional(CONF_PRECISION, default=1): cv.positive_int,
        vol.Optional(CONF_SCALE, default=1): vol.Coerce(float),
        vol.Optional(CONF_OFFSET, default=0): vol.Coerce(float),
        vol.Optional(CONF_MAX_TEMP, default=5): cv.positive_int,
        vol.Optional(CONF_MIN_TEMP, default=35): cv.positive_int,
        vol.Optional(CONF_STEP, default=0.5): vol.Coerce(float),
        vol.Optional(CONF_UNIT, default="C"): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Modbus Thermostat Platform."""
    name = config.get(CONF_NAME)
    modbus_slave = config.get(CONF_SLAVE)
    target_temp_register = config.get(CONF_TARGET_TEMP)
    current_temp_register = config.get(CONF_CURRENT_TEMP)
    data_type = config.get(CONF_DATA_TYPE)
    count = config.get(CONF_COUNT)
    precision = config.get(CONF_PRECISION)
    scale = config.get(CONF_SCALE)
    offset = config.get(CONF_OFFSET)
    unit = config.get(CONF_UNIT)
    max_temp = config.get(CONF_MAX_TEMP)
    min_temp = config.get(CONF_MIN_TEMP)
    temp_step = config.get(CONF_STEP)
    hub_name = config.get(CONF_HUB)
    hub = hass.data[MODBUS_DOMAIN][hub_name]

    add_entities(
        [
            ModbusThermostat(
                hub,
                name,
                modbus_slave,
                target_temp_register,
                current_temp_register,
                data_type,
                count,
                precision,
                scale,
                offset,
                unit,
                max_temp,
                min_temp,
                temp_step,
            )
        ],
        True,
    )


class ModbusThermostat(ClimateDevice):
    """Representation of a Modbus Thermostat."""

    def __init__(
        self,
        hub,
        name,
        modbus_slave,
        target_temp_register,
        current_temp_register,
        data_type,
        count,
        precision,
        scale,
        offset,
        unit,
        max_temp,
        min_temp,
        temp_step,
    ):
        """Initialize the unit."""
        self._hub = hub
        self._name = name
        self._slave = modbus_slave
        self._target_temperature_register = target_temp_register
        self._current_temperature_register = current_temp_register
        self._target_temperature = None
        self._current_temperature = None
        self._data_type = data_type
        self._count = int(count)
        self._precision = precision
        self._scale = scale
        self._offset = offset
        self._unit = unit
        self._max_temp = max_temp
        self._min_temp = min_temp
        self._temp_step = temp_step
        self._structure = ">f"

        data_types = {
            DATA_TYPE_INT: {1: "h", 2: "i", 4: "q"},
            DATA_TYPE_UINT: {1: "H", 2: "I", 4: "Q"},
            DATA_TYPE_FLOAT: {1: "e", 2: "f", 4: "d"},
        }

        self._structure = ">{}".format(data_types[self._data_type][self._count])

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    def update(self):
        """Update Target & Current Temperature."""
        self._target_temperature = self.read_register(self._target_temperature_register)
        self._current_temperature = self.read_register(
            self._current_temperature_register
        )

    @property
    def hvac_mode(self):
        """Return the current HVAC mode."""
        return HVAC_MODE_AUTO

    @property
    def hvac_modes(self):
        """Return the possible HVAC modes."""
        return HVAC_MODES

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._target_temperature

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT if self._unit == "F" else TEMP_CELSIUS

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._max_temp

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._temp_step

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temperature = int(
            (kwargs.get(ATTR_TEMPERATURE) - self._offset) / self._scale
        )
        if target_temperature is None:
            return
        byte_string = struct.pack(self._structure, target_temperature)
        register_value = struct.unpack(">h", byte_string[0:2])[0]

        try:
            self.write_register(self._target_temperature_register, register_value)
        except AttributeError as ex:
            _LOGGER.error(ex)

    def read_register(self, register):
        """Read holding register using the Modbus hub slave."""
        try:
            result = self._hub.read_holding_registers(
                self._slave, register, self._count
            )
        except AttributeError as ex:
            _LOGGER.error(ex)
        byte_string = b"".join(
            [x.to_bytes(2, byteorder="big") for x in result.registers]
        )
        val = struct.unpack(self._structure, byte_string)[0]
        register_value = format(
            (self._scale * val) + self._offset, f".{self._precision}f"
        )
        register_value = float(register_value)
        return register_value

    def write_register(self, register, value):
        """Write register using the Modbus hub slave."""
        self._hub.write_registers(self._slave, register, [value, 0])
