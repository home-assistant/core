"""Support for Modbus Register sensors."""
import logging
import struct
from typing import Any, Optional, Union

from pymodbus.exceptions import ConnectionException, ModbusException
from pymodbus.pdu import ExceptionResponse
import voluptuous as vol

from homeassistant.components.sensor import DEVICE_CLASSES_SCHEMA, PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_OFFSET,
    CONF_SLAVE,
    CONF_STRUCTURE,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_COUNT,
    CONF_DATA_TYPE,
    CONF_HUB,
    CONF_PRECISION,
    CONF_REGISTER,
    CONF_REGISTER_TYPE,
    CONF_REGISTERS,
    CONF_REVERSE_ORDER,
    CONF_SCALE,
    DATA_TYPE_CUSTOM,
    DATA_TYPE_FLOAT,
    DATA_TYPE_INT,
    DATA_TYPE_STRING,
    DATA_TYPE_UINT,
    DEFAULT_HUB,
    MODBUS_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def number(value: Any) -> Union[int, float]:
    """Coerce a value to number without losing precision."""
    if isinstance(value, int):
        return value

    if isinstance(value, str):
        try:
            value = int(value)
            return value
        except (TypeError, ValueError):
            pass

    try:
        value = float(value)
        return value
    except (TypeError, ValueError):
        raise vol.Invalid(f"invalid number {value}")


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_REGISTERS): [
            {
                vol.Required(CONF_NAME): cv.string,
                vol.Required(CONF_REGISTER): cv.positive_int,
                vol.Optional(CONF_COUNT, default=1): cv.positive_int,
                vol.Optional(CONF_DATA_TYPE, default=DATA_TYPE_INT): vol.In(
                    [
                        DATA_TYPE_INT,
                        DATA_TYPE_UINT,
                        DATA_TYPE_FLOAT,
                        DATA_TYPE_STRING,
                        DATA_TYPE_CUSTOM,
                    ]
                ),
                vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
                vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
                vol.Optional(CONF_OFFSET, default=0): number,
                vol.Optional(CONF_PRECISION, default=0): cv.positive_int,
                vol.Optional(
                    CONF_REGISTER_TYPE, default=CALL_TYPE_REGISTER_HOLDING
                ): vol.In([CALL_TYPE_REGISTER_HOLDING, CALL_TYPE_REGISTER_INPUT]),
                vol.Optional(CONF_REVERSE_ORDER, default=False): cv.boolean,
                vol.Optional(CONF_SCALE, default=1): number,
                vol.Optional(CONF_SLAVE): cv.positive_int,
                vol.Optional(CONF_STRUCTURE): cv.string,
                vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
            }
        ]
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Modbus sensors."""
    sensors = []
    data_types = {
        DATA_TYPE_INT: {1: "h", 2: "i", 4: "q"},
        DATA_TYPE_UINT: {1: "H", 2: "I", 4: "Q"},
        DATA_TYPE_FLOAT: {1: "e", 2: "f", 4: "d"},
    }

    for register in config[CONF_REGISTERS]:
        structure = ">i"
        if register[CONF_DATA_TYPE] == DATA_TYPE_STRING:
            structure = str(register[CONF_COUNT] * 2) + "s"
        elif register[CONF_DATA_TYPE] != DATA_TYPE_CUSTOM:
            try:
                structure = (
                    f">{data_types[register[CONF_DATA_TYPE]][register[CONF_COUNT]]}"
                )
            except KeyError:
                _LOGGER.error(
                    "Unable to detect data type for %s sensor, try a custom type",
                    register[CONF_NAME],
                )
                continue
        else:
            structure = register.get(CONF_STRUCTURE)

        try:
            size = struct.calcsize(structure)
        except struct.error as err:
            _LOGGER.error("Error in sensor %s structure: %s", register[CONF_NAME], err)
            continue

        if register[CONF_COUNT] * 2 != size:
            _LOGGER.error(
                "Structure size (%d bytes) mismatch registers count (%d words)",
                size,
                register[CONF_COUNT],
            )
            continue

        hub_name = register[CONF_HUB]
        hub = hass.data[MODBUS_DOMAIN][hub_name]
        sensors.append(
            ModbusRegisterSensor(
                hub,
                register[CONF_NAME],
                register.get(CONF_SLAVE),
                register[CONF_REGISTER],
                register[CONF_REGISTER_TYPE],
                register.get(CONF_UNIT_OF_MEASUREMENT),
                register[CONF_COUNT],
                register[CONF_REVERSE_ORDER],
                register[CONF_SCALE],
                register[CONF_OFFSET],
                structure,
                register[CONF_PRECISION],
                register[CONF_DATA_TYPE],
                register.get(CONF_DEVICE_CLASS),
            )
        )

    if not sensors:
        return False
    add_entities(sensors)


class ModbusRegisterSensor(RestoreEntity):
    """Modbus register sensor."""

    def __init__(
        self,
        hub,
        name,
        slave,
        register,
        register_type,
        unit_of_measurement,
        count,
        reverse_order,
        scale,
        offset,
        structure,
        precision,
        data_type,
        device_class,
    ):
        """Initialize the modbus register sensor."""
        self._hub = hub
        self._name = name
        self._slave = int(slave) if slave else None
        self._register = int(register)
        self._register_type = register_type
        self._unit_of_measurement = unit_of_measurement
        self._count = int(count)
        self._reverse_order = reverse_order
        self._scale = scale
        self._offset = offset
        self._precision = precision
        self._structure = structure
        self._data_type = data_type
        self._device_class = device_class
        self._value = None
        self._available = True

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        state = await self.async_get_last_state()
        if not state:
            return
        self._value = state.state

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

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    def update(self):
        """Update the state of the sensor."""
        try:
            if self._register_type == CALL_TYPE_REGISTER_INPUT:
                result = self._hub.read_input_registers(
                    self._slave, self._register, self._count
                )
            else:
                result = self._hub.read_holding_registers(
                    self._slave, self._register, self._count
                )
        except ConnectionException:
            self._available = False
            return

        if isinstance(result, (ModbusException, ExceptionResponse)):
            self._available = False
            return

        registers = result.registers
        if self._reverse_order:
            registers.reverse()

        byte_string = b"".join([x.to_bytes(2, byteorder="big") for x in registers])
        if self._data_type != DATA_TYPE_STRING:
            val = struct.unpack(self._structure, byte_string)[0]
            val = self._scale * val + self._offset
            if isinstance(val, int):
                self._value = str(val)
                if self._precision > 0:
                    self._value += "." + "0" * self._precision
            else:
                self._value = f"{val:.{self._precision}f}"
        else:
            self._value = byte_string.decode()

        self._available = True
