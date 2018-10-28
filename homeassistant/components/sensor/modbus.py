"""
Support for Modbus Register sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.modbus/
"""
import logging
import struct
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.modbus import CONF_HUB_NAME, DOMAIN
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_OFFSET, CONF_SLAVE,
                                 CONF_STRUCTURE, CONF_UNIT_OF_MEASUREMENT)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from pymodbus.client.sync import BaseModbusClient

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["modbus"]

CONF_COUNT = "count"
CONF_REVERSE_ORDER = "reverse_order"
CONF_PRECISION = "precision"
CONF_REGISTER = "register"
CONF_REGISTERS = "registers"
CONF_SCALE = "scale"
CONF_DATA_TYPE = "data_type"
CONF_REGISTER_TYPE = "register_type"

REGISTER_TYPE_HOLDING = "holding"
REGISTER_TYPE_INPUT = "input"

DATA_TYPE_INT = "int"
DATA_TYPE_UINT = "uint"
DATA_TYPE_FLOAT = "float"
DATA_TYPE_CUSTOM = "custom"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_REGISTERS): [{
        vol.Required(CONF_HUB_NAME, default="default"):
            cv.string,
        vol.Required(CONF_NAME):
            cv.string,
        vol.Required(CONF_REGISTER):
            cv.positive_int,
        vol.Optional(CONF_REGISTER_TYPE, default=REGISTER_TYPE_HOLDING):
            vol.In([REGISTER_TYPE_HOLDING, REGISTER_TYPE_INPUT]),
        vol.Optional(CONF_COUNT, default=1):
            cv.positive_int,
        vol.Optional(CONF_REVERSE_ORDER, default=False):
            cv.boolean,
        vol.Optional(CONF_OFFSET, default=0):
            vol.Coerce(float),
        vol.Optional(CONF_PRECISION, default=0):
            cv.positive_int,
        vol.Optional(CONF_SCALE, default=1):
            vol.Coerce(float),
        vol.Optional(CONF_SLAVE):
            cv.positive_int,
        vol.Optional(CONF_DATA_TYPE, default=DATA_TYPE_INT):
            vol.In([
                DATA_TYPE_INT, DATA_TYPE_UINT, DATA_TYPE_FLOAT,
                DATA_TYPE_CUSTOM
            ]),
        vol.Optional(CONF_STRUCTURE):
            cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT):
            cv.string,
    }]
})


def setup_platform(hass: Any,
                   config: dict,
                   add_devices: Any,
                   discovery_info: Any = None) -> bool:
    """Set up the Modbus sensors."""
    sensors = []
    data_types = {DATA_TYPE_INT: {1: "h", 2: "i", 4: "q"}}
    data_types[DATA_TYPE_UINT] = {1: "H", 2: "I", 4: "Q"}
    data_types[DATA_TYPE_FLOAT] = {1: "e", 2: "f", 4: "d"}

    for register in config.get(CONF_REGISTERS, []):
        structure = ">i"
        if register.get(CONF_DATA_TYPE) != DATA_TYPE_CUSTOM:
            try:
                structure = ">{}".format(data_types[register.get(
                    CONF_DATA_TYPE)][register.get(CONF_COUNT)])
            except KeyError:
                _LOGGER.error(
                    "Unable to detect data type for %s sensor, "
                    "try a custom type.",
                    register.get(CONF_NAME),
                )
                continue
        else:
            structure = register.get(CONF_STRUCTURE)

        try:
            size = struct.calcsize(structure)
        except struct.error as err:
            _LOGGER.error("Error in sensor %s structure: %s",
                          register.get(CONF_NAME), err)
            continue

        if register.get(CONF_COUNT) * 2 != size:
            _LOGGER.error(
                "Structure size (%d bytes) mismatch registers count "
                "(%d words)",
                size,
                register.get(CONF_COUNT),
            )
            continue

        hub_name = register.get(CONF_HUB_NAME)
        hub = hass.data[DOMAIN][hub_name]
        sensors.append(
            ModbusRegisterSensor(
                hub,
                register.get(CONF_NAME),
                register.get(CONF_SLAVE),
                register.get(CONF_REGISTER),
                register.get(CONF_REGISTER_TYPE),
                register.get(CONF_UNIT_OF_MEASUREMENT),
                register.get(CONF_COUNT),
                register.get(CONF_REVERSE_ORDER),
                register.get(CONF_SCALE),
                register.get(CONF_OFFSET),
                structure,
                register.get(CONF_PRECISION),
            ))

    if not sensors:
        return False
    add_devices(sensors)
    return True


class ModbusRegisterSensor(Entity):
    """Modbus register sensor."""

    def __init__(self, hub, name, slave, register, register_type,
                 unit_of_measurement, count, reverse_order, scale, offset,
                 structure, precision):
        """Initialize the modbus register sensor."""
        self._hub: "BaseModbusClient" = hub
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
        self._value: str = None

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._value

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._unit_of_measurement

    def update(self) -> None:
        """Update the state of the sensor."""
        if self._register_type == REGISTER_TYPE_INPUT:
            result = self._hub.read_input_registers(
                self._slave, self._register, self._count)
        else:
            result = self._hub.read_holding_registers(
                self._slave, self._register, self._count)
        val = 0

        try:
            registers = result.registers
            if self._reverse_order:
                registers.reverse()
        except AttributeError:
            _LOGGER.error(
                "No response from modbus slave %s, register %s",
                self._slave,
                self._register,
            )
            return
        byte_string = b"".join(
            [x.to_bytes(2, byteorder="big") for x in registers])
        val = struct.unpack(self._structure, byte_string)[0]
        self._value = format(self._scale * val + self._offset,
                             ".{}f".format(self._precision))
