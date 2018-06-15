"""
Platform for a Generic Modbus Thermostat.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.modbus/
"""

import logging
import struct

import voluptuous as vol

from homeassistant.components.climate import (
    ClimateDevice, SUPPORT_TARGET_TEMPERATURE, SUPPORT_TARGET_HUMIDITY,
    SUPPORT_OPERATION_MODE, SUPPORT_FAN_MODE, SUPPORT_SWING_MODE,
    SUPPORT_HOLD_MODE, SUPPORT_AWAY_MODE, SUPPORT_AUX_HEAT, SUPPORT_ON_OFF,
    SUPPORT_TARGET_HUMIDITY_HIGH, SUPPORT_TARGET_HUMIDITY_LOW,
    PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_NAME, CONF_SLAVE, CONF_OFFSET, CONF_STRUCTURE, ATTR_TEMPERATURE)
from homeassistant.helpers.event import async_call_later
import homeassistant.components.modbus as modbus
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['modbus']

CONF_TEMPERATURE = 'temperature'
CONF_TARGET_TEMPERATURE = 'target_temperature'
CONF_HUMIDITY = 'humidity'
CONF_TARGET_HUMIDITY = 'target_humidity'
CONF_OPERATION = 'operation'
CONF_FAN = 'fan'
CONF_SWING = 'swing'
CONF_HOLD = 'hold'
CONF_AWAY = 'away'
CONF_AUX = 'aux'
CONF_IS_ON = 'is_on'

CONF_OPERATION_LIST = 'operation_list'
CONF_FAN_LIST = 'fan_list'
CONF_SWING_LIST = 'swing_list'

CONF_COUNT = 'count'
CONF_DATA_TYPE = 'data_type'
CONF_REGISTER = 'register'
CONF_REGISTER_TYPE = 'register_type'
CONF_REGISTERS = 'registers'
CONF_REVERSE_ORDER = 'reverse_order'
CONF_SCALE = 'scale'

REGISTER_TYPE_HOLDING = 'holding'
REGISTER_TYPE_INPUT = 'input'
REGISTER_TYPE_COIL = 'coil'

DATA_TYPE_INT = 'int'
DATA_TYPE_UINT = 'uint'
DATA_TYPE_FLOAT = 'float'
DATA_TYPE_CUSTOM = 'custom'

SUPPORTED_FEATURES = {
    CONF_TEMPERATURE: 0,
    CONF_TARGET_TEMPERATURE: SUPPORT_TARGET_TEMPERATURE,
    CONF_HUMIDITY: 0,
    CONF_TARGET_HUMIDITY: (SUPPORT_TARGET_HUMIDITY |
                           SUPPORT_TARGET_HUMIDITY_LOW |
                           SUPPORT_TARGET_HUMIDITY_HIGH),
    CONF_OPERATION: SUPPORT_OPERATION_MODE,
    CONF_FAN: SUPPORT_FAN_MODE,
    CONF_SWING: SUPPORT_SWING_MODE,
    CONF_HOLD: SUPPORT_HOLD_MODE,
    CONF_AWAY: SUPPORT_AWAY_MODE,
    CONF_AUX: SUPPORT_AUX_HEAT,
    CONF_IS_ON: SUPPORT_ON_OFF
    }

DEFAULT_NAME = 'Modbus'
DEFAULT_OPERATION_LIST = ['heat', 'cool', 'auto', 'off']
DEFAULT_FAN_LIST = ['On Low', 'On High', 'Auto Low', 'Auto High', 'Off']
DEFAULT_SWING_LIST = ['Auto', '1', '2', '3', 'Off']


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_OPERATION_LIST, default=DEFAULT_OPERATION_LIST):
        vol.All(cv.ensure_list, vol.Length(min=2)),
    vol.Optional(CONF_FAN_LIST, default=DEFAULT_FAN_LIST):
        vol.All(cv.ensure_list, vol.Length(min=2)),
    vol.Optional(CONF_SWING_LIST, default=DEFAULT_SWING_LIST):
        vol.All(cv.ensure_list, vol.Length(min=2)),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Modbus Thermostat Platform."""
    name = config.get(CONF_NAME)
    operation_list = config.get(CONF_OPERATION_LIST)
    fan_list = config.get(CONF_FAN_LIST)
    swing_list = config.get(CONF_SWING_LIST)

    data_types = {DATA_TYPE_INT: {1: 'h', 2: 'i', 4: 'q'}}
    data_types[DATA_TYPE_UINT] = {1: 'H', 2: 'I', 4: 'Q'}
    data_types[DATA_TYPE_FLOAT] = {1: 'e', 2: 'f', 4: 'd'}

    mods = {}
    for prop in SUPPORTED_FEATURES:
        mod = config.get(prop)
        if not mod:
            continue

        count = mod[CONF_COUNT] if CONF_COUNT in mod else 1
        data_type = mod.get(CONF_DATA_TYPE)
        if data_type != DATA_TYPE_CUSTOM:
            try:
                mod[CONF_STRUCTURE] = '>{}'.format(data_types[
                    DATA_TYPE_INT if data_type is None else data_type][count])
            except KeyError:
                _LOGGER.error("Unable to detect data type for %s", prop)
                continue

        try:
            size = struct.calcsize(mod[CONF_STRUCTURE])
        except struct.error as err:
            _LOGGER.error(
                "Error in sensor %s structure: %s", prop, err)
            continue

        if count * 2 != size:
            _LOGGER.error(
                "Structure size (%d bytes) mismatch registers count "
                "(%d words)", size, count)
            continue

        mods[prop] = mod

    if not mods:
        _LOGGER.error("Invalid config %s: no modbus items", name)
        return

    def has_valid_register(mods, index):
        """Check valid register."""
        for prop in mods:
            registers = mods[prop].get(CONF_REGISTERS)
            if not registers or index >= len(registers):
                return False
        return True

    devices = []
    for index in range(100):
        if not has_valid_register(mods, index):
            break
        devices.append(ModbusClimate(name, operation_list, fan_list,
                                     swing_list, mods, index))

    if not devices:
        for prop in mods:
            if CONF_REGISTER not in mods[prop]:
                _LOGGER.error("Invalid config %s/%s: no register", name, prop)
                return
        devices.append(ModbusClimate(name, operation_list, fan_list,
                                     swing_list, mods))

    add_devices(devices, True)


class ModbusClimate(ClimateDevice):
    """Representation of a Modbus climate device."""

    def __init__(self, name, operation_list,
                 fan_list, swing_list, mods, index=-1):
        """Initialize the climate device."""
        self._name = name + str(index + 1) if index != -1 else name
        self._index = index
        self._mods = mods
        self._operation_list = operation_list
        self._fan_list = fan_list
        self._swing_list = swing_list
        self._values = {}

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def supported_features(self):
        """Return the list of supported features."""
        features = 0
        for prop in self._mods:
            features |= SUPPORTED_FEATURES[prop]
        return features

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self.unit_of_measurement

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.get_value(CONF_TEMPERATURE)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.get_value(CONF_TARGET_TEMPERATURE)

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self.get_value(CONF_HUMIDITY)

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self.get_value(CONF_TARGET_HUMIDITY)

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        if not self.is_on:
            return 'off'

        operation = self.get_value(CONF_OPERATION)
        if operation is not None and operation < len(self._operation_list):
            return self._operation_list[operation]
        return None

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        fan = self.get_value(CONF_FAN)
        if fan is not None and fan < len(self._fan_list):
            return self._fan_list[fan]
        return None

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return self._fan_list

    @property
    def current_swing_mode(self):
        """Return the swing setting."""
        swing = self.get_value(CONF_SWING)
        if swing is not None and swing < len(self._swing_list):
            return self._swing_list[swing]
        return None

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._swing_list

    @property
    def current_hold_mode(self):
        """Return hold mode setting."""
        return self.get_value(CONF_HOLD)

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self.get_value(CONF_AWAY)

    @property
    def is_aux_heat_on(self):
        """Return true if aux heat is on."""
        return self.get_value(CONF_AUX)

    @property
    def is_on(self):
        """Return true if the device is on."""
        return self.get_value(CONF_IS_ON)
        
    def try_reconnect(self):
        from pymodbus.client.sync import ModbusTcpClient as ModbusClient
        from pymodbus.transaction import ModbusRtuFramer as ModbusFramer
        client = ModbusClient(host=modbus.HUB._client.host,
                              port=modbus.HUB._client.port,
                              framer=ModbusFramer,
                              timeout=modbus.HUB._client.timeout)
        _LOGGER.error("Reconnect: %s", client)
        modbus.HUB._client = client
        modbus.HUB._client.connect()

    def update(self):
        """Update state."""
        for prop in self._mods:
            mod = self._mods[prop]
            register_type, slave, register, scale, offset = \
                self.register_info(mod)
            count = mod[CONF_COUNT] if CONF_COUNT in mod else 1

            if register_type == REGISTER_TYPE_COIL:
                result = modbus.HUB.read_coils(slave, register, count)
                try:
                	value = bool(result.bits[0])
                except:
                    _LOGGER.error("No response from %s %s", self._name, prop)
                    self.try_reconnect()
                    return
            else:
                try:
                    if register_type == REGISTER_TYPE_INPUT:
                        result = modbus.HUB.read_input_registers(slave,
                                                             register, count)
                    else:
                        result = modbus.HUB.read_holding_registers(slave,
                                                               register, count)

                    val = 0
                    registers = result.registers
                    if mod.get(CONF_REVERSE_ORDER):
                        registers.reverse()
                except:
                    _LOGGER.error("No response from %s %s", self._name, prop)
                    self.try_reconnect()
                    return

                byte_string = b''.join(
                    [x.to_bytes(2, byteorder='big') for x in registers]
                )
                val = struct.unpack(mod[CONF_STRUCTURE], byte_string)[0]
                value = scale * val + offset

            _LOGGER.info("Read %s: %s = %f", self.name, prop, value)
            self._values[prop] = value

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            self.set_value(CONF_TARGET_TEMPERATURE, temperature)

    def set_humidity(self, humidity):
        """Set new target humidity."""
        self.set_value(CONF_TARGET_HUMIDITY, humidity)

    def set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        try:
            is_on = operation_mode != 'off'
            self.set_value(CONF_IS_ON, is_on)
            if is_on:
                if operation_mode == 'auto':
                    current = self.current_temperature
                    target = self.target_temperature
                    operation_mode = 'heat' \
                        if current and target and current < target else 'cool'
                index = self._operation_list.index(operation_mode)
                self.set_value(CONF_OPERATION, index)
        except ValueError:
            _LOGGER.error("Invalid operation_mode: %s", operation_mode)

    def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        try:
            index = self._fan_list.index(fan_mode)
            self.set_value(CONF_FAN, index)
        except ValueError:
            _LOGGER.error("Invalid fan_mode: %s", fan_mode)

    def set_swing_mode(self, swing_mode):
        """Set new swing mode."""
        try:
            index = self._swing_list.index(swing_mode)
            self.set_value(CONF_SWING, index)
        except ValueError:
            _LOGGER.error("Invalid swing_mode: %s", swing_mode)

    def set_hold_mode(self, hold_mode):
        """Set new hold mode."""
        self.set_value(CONF_HOLD, hold_mode)

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self.set_value(CONF_AWAY, True)

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self.set_value(CONF_AWAY, False)

    def turn_aux_heat_on(self):
        """Turn auxiliary heater on."""
        self.set_value(CONF_AUX, True)

    def turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        self.set_value(CONF_AUX, False)

    def turn_on(self):
        """Turn on."""
        self.set_value(CONF_IS_ON, True)

    def turn_off(self):
        """Turn off."""
        self.set_value(CONF_IS_ON, False)

    def register_info(self, mod):
        """Get register info."""
        register_type = mod.get(CONF_REGISTER_TYPE)
        register = mod[CONF_REGISTER] \
            if self._index == -1 else mod[CONF_REGISTERS][self._index]
        slave = mod[CONF_SLAVE] if CONF_SLAVE in mod else 1
        scale = mod[CONF_SCALE] if CONF_SCALE in mod else 1
        offset = mod[CONF_OFFSET] if CONF_OFFSET in mod else 0
        return (register_type, slave, register, scale, offset)

    def get_value(self, prop):
        """Get property value."""
        return self._values.get(prop)

    def set_value(self, prop, value):
        """Set property value."""
        mod = self._mods[prop]
        register_type, slave, register, scale, offset = self.register_info(mod)
        _LOGGER.info("Write %s: %s = %f", self.name, prop, value)

        if register_type == REGISTER_TYPE_COIL:
            modbus.HUB.write_coil(slave, register, bool(value))
        else:
            val = (value - offset) / scale
            modbus.HUB.write_register(slave, register, int(val))

        self._values[prop] = value

        async_call_later(self.hass, 2, self.async_schedule_update_ha_state)
