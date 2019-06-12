"""Support for Modbus switches."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_COMMAND_OFF, CONF_COMMAND_ON, CONF_NAME, CONF_SLAVE, STATE_ON)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.restore_state import RestoreEntity

from . import CONF_HUB, DEFAULT_HUB, DOMAIN as MODBUS_DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_COIL = 'coil'
CONF_COILS = 'coils'
CONF_REGISTER = 'register'
CONF_REGISTER_TYPE = 'register_type'
CONF_REGISTERS = 'registers'
CONF_STATE_OFF = 'state_off'
CONF_STATE_ON = 'state_on'
CONF_VERIFY_REGISTER = 'verify_register'
CONF_VERIFY_STATE = 'verify_state'

REGISTER_TYPE_HOLDING = 'holding'
REGISTER_TYPE_INPUT = 'input'

REGISTERS_SCHEMA = vol.Schema({
    vol.Required(CONF_COMMAND_OFF): cv.positive_int,
    vol.Required(CONF_COMMAND_ON): cv.positive_int,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_REGISTER): cv.positive_int,
    vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
    vol.Optional(CONF_REGISTER_TYPE, default=REGISTER_TYPE_HOLDING):
        vol.In([REGISTER_TYPE_HOLDING, REGISTER_TYPE_INPUT]),
    vol.Optional(CONF_SLAVE): cv.positive_int,
    vol.Optional(CONF_STATE_OFF): cv.positive_int,
    vol.Optional(CONF_STATE_ON): cv.positive_int,
    vol.Optional(CONF_VERIFY_REGISTER): cv.positive_int,
    vol.Optional(CONF_VERIFY_STATE, default=True): cv.boolean,
})

COILS_SCHEMA = vol.Schema({
    vol.Required(CONF_COIL): cv.positive_int,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_SLAVE): cv.positive_int,
    vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
})

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_COILS, CONF_REGISTERS),
    PLATFORM_SCHEMA.extend({
        vol.Optional(CONF_COILS): [COILS_SCHEMA],
        vol.Optional(CONF_REGISTERS): [REGISTERS_SCHEMA],
    }))


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Read configuration and create Modbus devices."""
    switches = []
    if CONF_COILS in config:
        for coil in config.get(CONF_COILS):
            hub_name = coil.get(CONF_HUB)
            hub = hass.data[MODBUS_DOMAIN][hub_name]
            switches.append(ModbusCoilSwitch(
                hub, coil.get(CONF_NAME), coil.get(CONF_SLAVE),
                coil.get(CONF_COIL)))
    if CONF_REGISTERS in config:
        for register in config.get(CONF_REGISTERS):
            hub_name = register.get(CONF_HUB)
            hub = hass.data[MODBUS_DOMAIN][hub_name]

            switches.append(ModbusRegisterSwitch(
                hub,
                register.get(CONF_NAME),
                register.get(CONF_SLAVE),
                register.get(CONF_REGISTER),
                register.get(CONF_COMMAND_ON),
                register.get(CONF_COMMAND_OFF),
                register.get(CONF_VERIFY_STATE),
                register.get(CONF_VERIFY_REGISTER),
                register.get(CONF_REGISTER_TYPE),
                register.get(CONF_STATE_ON),
                register.get(CONF_STATE_OFF)))

    add_entities(switches)


class ModbusCoilSwitch(ToggleEntity, RestoreEntity):
    """Representation of a Modbus coil switch."""

    def __init__(self, hub, name, slave, coil):
        """Initialize the coil switch."""
        self._hub = hub
        self._name = name
        self._slave = int(slave) if slave else None
        self._coil = int(coil)
        self._is_on = None

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        state = await self.async_get_last_state()
        if not state:
            return
        self._is_on = state.state == STATE_ON

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    def turn_on(self, **kwargs):
        """Set switch on."""
        self._hub.write_coil(self._slave, self._coil, True)

    def turn_off(self, **kwargs):
        """Set switch off."""
        self._hub.write_coil(self._slave, self._coil, False)

    def update(self):
        """Update the state of the switch."""
        result = self._hub.read_coils(self._slave, self._coil, 1)
        try:
            self._is_on = bool(result.bits[0])
        except AttributeError:
            _LOGGER.error(
                'No response from hub %s, slave %s, coil %s',
                self._hub.name, self._slave, self._coil)


class ModbusRegisterSwitch(ModbusCoilSwitch):
    """Representation of a Modbus register switch."""

    # pylint: disable=super-init-not-called
    def __init__(self, hub, name, slave, register, command_on, command_off,
                 verify_state, verify_register, register_type, state_on,
                 state_off):
        """Initialize the register switch."""
        self._hub = hub
        self._name = name
        self._slave = slave
        self._register = register
        self._command_on = command_on
        self._command_off = command_off
        self._verify_state = verify_state
        self._verify_register = (
            verify_register if verify_register else self._register)
        self._register_type = register_type

        if state_on is not None:
            self._state_on = state_on
        else:
            self._state_on = self._command_on

        if state_off is not None:
            self._state_off = state_off
        else:
            self._state_off = self._command_off

        self._is_on = None

    def turn_on(self, **kwargs):
        """Set switch on."""
        self._hub.write_register(self._slave, self._register, self._command_on)
        if not self._verify_state:
            self._is_on = True

    def turn_off(self, **kwargs):
        """Set switch off."""
        self._hub.write_register(
            self._slave, self._register, self._command_off)
        if not self._verify_state:
            self._is_on = False

    def update(self):
        """Update the state of the switch."""
        if not self._verify_state:
            return

        value = 0
        if self._register_type == REGISTER_TYPE_INPUT:
            result = self._hub.read_input_registers(
                self._slave, self._register, 1)
        else:
            result = self._hub.read_holding_registers(
                self._slave, self._register, 1)

        try:
            value = int(result.registers[0])
        except AttributeError:
            _LOGGER.error(
                "No response from hub %s, slave %s, register %s",
                self._hub.name, self._slave, self._verify_register)

        if value == self._state_on:
            self._is_on = True
        elif value == self._state_off:
            self._is_on = False
        else:
            _LOGGER.error(
                "Unexpected response from hub %s, slave %s "
                "register %s, got 0x%2x",
                self._hub.name, self._slave, self._verify_register, value)
