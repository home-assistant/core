"""Support for Generic Modbus Thermostats."""
import logging
import struct
from typing import Optional

from pymodbus.exceptions import ConnectionException, ModbusException
from pymodbus.pdu import ExceptionResponse
import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
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

from .const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_CURRENT_TEMP,
    CONF_CURRENT_TEMP_REGISTER_TYPE,
    CONF_DATA_COUNT,
    CONF_DATA_TYPE,
    CONF_HUB,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_OFFSET,
    CONF_PRECISION,
    CONF_SCALE,
    CONF_STEP,
    CONF_TARGET_TEMP,
    CONF_UNIT,
    DATA_TYPE_FLOAT,
    DATA_TYPE_INT,
    DATA_TYPE_UINT,
    DEFAULT_HUB,
    MODBUS_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_CURRENT_TEMP): cv.positive_int,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_SLAVE): cv.positive_int,
        vol.Required(CONF_TARGET_TEMP): cv.positive_int,
        vol.Optional(CONF_DATA_COUNT, default=2): cv.positive_int,
        vol.Optional(
            CONF_CURRENT_TEMP_REGISTER_TYPE, default=CALL_TYPE_REGISTER_HOLDING
        ): vol.In([CALL_TYPE_REGISTER_HOLDING, CALL_TYPE_REGISTER_INPUT]),
        vol.Optional(CONF_DATA_TYPE, default=DATA_TYPE_FLOAT): vol.In(
            [DATA_TYPE_INT, DATA_TYPE_UINT, DATA_TYPE_FLOAT]
        ),
        vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
        vol.Optional(CONF_PRECISION, default=1): cv.positive_int,
        vol.Optional(CONF_SCALE, default=1): vol.Coerce(float),
        vol.Optional(CONF_OFFSET, default=0): vol.Coerce(float),
        vol.Optional(CONF_MAX_TEMP, default=35): cv.positive_int,
        vol.Optional(CONF_MIN_TEMP, default=5): cv.positive_int,
        vol.Optional(CONF_STEP, default=0.5): vol.Coerce(float),
        vol.Optional(CONF_UNIT, default="C"): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Modbus Thermostat Platform."""
    name = config[CONF_NAME]
    modbus_slave = config[CONF_SLAVE]
    target_temp_register = config[CONF_TARGET_TEMP]
    current_temp_register = config[CONF_CURRENT_TEMP]
    current_temp_register_type = config[CONF_CURRENT_TEMP_REGISTER_TYPE]
    data_type = config[CONF_DATA_TYPE]
    count = config[CONF_DATA_COUNT]
    precision = config[CONF_PRECISION]
    scale = config[CONF_SCALE]
    offset = config[CONF_OFFSET]
    unit = config[CONF_UNIT]
    max_temp = config[CONF_MAX_TEMP]
    min_temp = config[CONF_MIN_TEMP]
    temp_step = config[CONF_STEP]
    hub_name = config[CONF_HUB]
    hub = hass.data[MODBUS_DOMAIN][hub_name]

    add_entities(
        [
            ModbusThermostat(
                hub,
                name,
                modbus_slave,
                target_temp_register,
                current_temp_register,
                current_temp_register_type,
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


class ModbusThermostat(ClimateEntity):
    """Representation of a Modbus Thermostat."""

    def __init__(
        self,
        hub,
        name,
        modbus_slave,
        target_temp_register,
        current_temp_register,
        current_temp_register_type,
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
        self._current_temperature_register_type = current_temp_register_type
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
        self._available = True

        data_types = {
            DATA_TYPE_INT: {1: "h", 2: "i", 4: "q"},
            DATA_TYPE_UINT: {1: "H", 2: "I", 4: "Q"},
            DATA_TYPE_FLOAT: {1: "e", 2: "f", 4: "d"},
        }

        self._structure = f">{data_types[self._data_type][self._count]}"

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    def update(self):
        """Update Target & Current Temperature."""
        self._target_temperature = self._read_register(
            CALL_TYPE_REGISTER_HOLDING, self._target_temperature_register
        )
        self._current_temperature = self._read_register(
            self._current_temperature_register_type, self._current_temperature_register
        )

    @property
    def hvac_mode(self):
        """Return the current HVAC mode."""
        return HVAC_MODE_AUTO

    @property
    def hvac_modes(self):
        """Return the possible HVAC modes."""
        return [HVAC_MODE_AUTO]

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
        self._write_register(self._target_temperature_register, register_value)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    def _read_register(self, register_type, register) -> Optional[float]:
        """Read register using the Modbus hub slave."""
        try:
            if register_type == CALL_TYPE_REGISTER_INPUT:
                result = self._hub.read_input_registers(
                    self._slave, register, self._count
                )
            else:
                result = self._hub.read_holding_registers(
                    self._slave, register, self._count
                )
        except ConnectionException:
            self._available = False
            return

        if isinstance(result, (ModbusException, ExceptionResponse)):
            self._available = False
            return

        byte_string = b"".join(
            [x.to_bytes(2, byteorder="big") for x in result.registers]
        )
        val = struct.unpack(self._structure, byte_string)[0]
        register_value = format(
            (self._scale * val) + self._offset, f".{self._precision}f"
        )
        register_value = float(register_value)
        self._available = True

        return register_value

    def _write_register(self, register, value):
        """Write holding register using the Modbus hub slave."""
        try:
            self._hub.write_registers(self._slave, register, [value, 0])
        except ConnectionException:
            self._available = False
            return

        self._available = True
