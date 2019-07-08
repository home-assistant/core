"""Support for Modbus sensors that follow the SunSpec specification."""
import logging

import voluptuous as vol
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME,
    CONF_SLAVE)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

MODBUS_DOMAIN = "modbus"
DEFAULT_HUB = 'default'
CONF_BASE_REGISTER = 'base_register'
CONF_MODEL = "model"
CONF_HUB = "hub"

# SunSpec model identifiers
SINGLE_PHASE_INVERTER_MODEL = 101
SPLIT_PHASE_INVERTER_MODEL = 102
THREE_PHASE_INVERTER_MODEL = 103
SINGLE_PHASE_METER_MODEL = 201
SPLIT_PHASE_METER_MODEL = 202
WYE_CONNECT_THREE_PHASE_METER_MODEL = 203
DELTA_CONNECT_THREE_PHASE_METER_MODEL = 204

# SunSpec block offsets
METER_AC_POWER_OFFSET = 18
METER_AC_POWER_SCALE_FACTOR_OFFSET = 4
INVERTER_AC_POWER_OFFSET = 14
INVERTER_AC_POWER_SCALE_FACTOR_OFFSET = 1


SUPPORTED_INVERTERS = [
    SINGLE_PHASE_INVERTER_MODEL,
    SPLIT_PHASE_INVERTER_MODEL,
    THREE_PHASE_INVERTER_MODEL
]

SUPPORTER_METERS = [
    SINGLE_PHASE_METER_MODEL,
    SPLIT_PHASE_METER_MODEL,
    WYE_CONNECT_THREE_PHASE_METER_MODEL,
    DELTA_CONNECT_THREE_PHASE_METER_MODEL
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MODEL): [{
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_BASE_REGISTER): cv.positive_int,
        vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
        vol.Optional(CONF_SLAVE): cv.positive_int,
    }]
})

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Setup the platform"""
    sensors = []

    for model in config.get(CONF_MODEL):
        hub_name = model.get(CONF_HUB)
        base_register = model.get(CONF_BASE_REGISTER)
        slave = model.get(CONF_SLAVE)

        hub = hass.data[MODBUS_DOMAIN][hub_name]
        try:
            model_id = get_sunspec_model_id(hub, base_register, slave)
        except AttributeError:
            _LOGGER.error("No response from hub %s, slave %s", hub_name, slave)
            return False

        if model_id in SUPPORTED_INVERTERS:
            sensors.append(SunSpecModbusInverter(
                hub,
                model.get(CONF_NAME),
                model.get(CONF_BASE_REGISTER),
                model.get(CONF_SLAVE)))

        if model_id in SUPPORTER_METERS:
            sensors.append(SunSpecModbusMeter(
                hub,
                model.get(CONF_NAME),
                model.get(CONF_BASE_REGISTER),
                model.get(CONF_SLAVE)))

    if not sensors:
        return False

    add_entities(sensors)
    return True

def get_sunspec_model_id(hub, base_register, slave):
    """Determine the id of a SunSpec model located at base_register"""
    result = hub.read_holding_registers(slave, base_register, 2)
    decoder = BinaryPayloadDecoder.fromRegisters(result.registers,
                                                 byteorder=Endian.Big,
                                                 wordorder=Endian.Big)
    return decoder.decode_16bit_uint()

def get_sunspec_scaled_register(hub, register, slave, value_offset, scale_factor_offset):
    """Implement an atomic read of a scaled value"""
    value_register = register + value_offset
    count = scale_factor_offset + 1
    result = hub.read_holding_registers(slave, value_register, count)

    decoder = BinaryPayloadDecoder.fromRegisters(result.registers,
                                                 byteorder=Endian.Big,
                                                 wordorder=Endian.Big)
    value = decoder.decode_16bit_int()
    decoder.skip_bytes(scale_factor_offset - 1)
    scale_factor = decoder.decode_16bit_int()

    return round(value * 10 ** scale_factor, 0)


class SunSpecModbusInverter(RestoreEntity):
    """Sunspec register sensor."""

    def __init__(self, hub, name, base_register, slave):
        """Initialize the SunSpec register sensor."""
        self._hub = hub
        self._name = name
        self._slave = int(slave) if slave else None
        self._base_register = int(base_register)
        self._value = None

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
        return "W"

    def update(self):
        """Update the state of the sensor."""
        try:
            self._value = get_sunspec_scaled_register(
                self._hub,
                self._base_register,
                self._slave,
                INVERTER_AC_POWER_OFFSET,
                INVERTER_AC_POWER_SCALE_FACTOR_OFFSET)
        except AttributeError:
            _LOGGER.error("No response from hub %s, slave %s", self._hub.name, self._slave)
            return

class SunSpecModbusMeter(RestoreEntity):
    """Sunspec register sensor."""

    def __init__(self, hub, name, base_register, slave):
        """Initialize the SunSpec register sensor."""
        self._hub = hub
        self._name = name
        self._slave = int(slave) if slave else None
        self._base_register = int(base_register)
        self._value = None

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
        return "W"

    def update(self):
        """Update the state of the sensor."""
        try:
            self._value = get_sunspec_scaled_register(self._hub,
                                                      self._base_register,
                                                      self._slave,
                                                      METER_AC_POWER_OFFSET,
                                                      METER_AC_POWER_SCALE_FACTOR_OFFSET)
        except AttributeError:
            _LOGGER.error("No response from hub %s, slave %s", self._hub.name, self._slave)
            return
