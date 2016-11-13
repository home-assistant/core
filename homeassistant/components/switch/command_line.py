"""
Support for custom shell commands to turn a switch on/off.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.command_line/
"""
import asyncio
import logging
import subprocess

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_FRIENDLY_NAME, CONF_SWITCHES, CONF_VALUE_TEMPLATE, CONF_COMMAND_OFF,
    CONF_COMMAND_ON, CONF_COMMAND_STATE)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

SWITCH_SCHEMA = vol.Schema({
    vol.Optional(CONF_COMMAND_OFF, default='true'): cv.string,
    vol.Optional(CONF_COMMAND_ON, default='true'): cv.string,
    vol.Optional(CONF_COMMAND_STATE): cv.string,
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SWITCHES): vol.Schema({cv.slug: SWITCH_SCHEMA}),
})


# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Find and return switches controlled by shell commands."""
    devices = config.get(CONF_SWITCHES, {})
    switches = []

    for device_name, device_config in devices.items():
        value_template = device_config.get(CONF_VALUE_TEMPLATE)

        if value_template is not None:
            value_template.hass = hass

        switches.append(
            CommandSwitch(
                hass,
                device_config.get(CONF_FRIENDLY_NAME, device_name),
                device_config.get(CONF_COMMAND_ON),
                device_config.get(CONF_COMMAND_OFF),
                device_config.get(CONF_COMMAND_STATE),
                value_template,
            )
        )

    if not switches:
        _LOGGER.error("No switches added")
        return False

    yield from async_add_devices(switches)


class CommandSwitch(SwitchDevice):
    """Representation a switch that can be toggled using shell commands."""

    def __init__(self, hass, name, command_on, command_off,
                 command_state, value_template):
        """Initialize the switch."""
        self._hass = hass
        self._name = name
        self._state = False
        self._command_on = command_on
        self._command_off = command_off
        self._command_state = command_state
        self._value_template = value_template

    @staticmethod
    @asyncio.coroutine
    def _async_switch(command):
        """Execute the actual commands."""
        _LOGGER.info('Running command: %s', command)

        proc = yield from asyncio.create_subprocess_shell(command)
        success = (yield from proc.wait()) == 0

        if not success:
            _LOGGER.error('Command failed: %s', command)

        return success

    @staticmethod
    @asyncio.coroutine
    def _async_query_state_value(command):
        """Execute state command for return value."""
        _LOGGER.info('Running state command: %s', command)

        proc = yield from asyncio.create_subprocess_shell(
            command, stdout=asyncio.subprocess.PIPE)
        return_value, _ = yield from proc.communicate()
        return return_value.strip().decode('utf-8')

    @staticmethod
    @asyncio.coroutine
    def _async_query_state_code(command):
        """Execute state command for return code."""
        _LOGGER.info('Running state command: %s', command)
        proc = yield from asyncio.create_subprocess_shell(command)
        return (yield from proc.wait()) == 0

    @property
    def should_poll(self):
        """Only poll if we have state command."""
        return self._command_state is not None

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._command_state is False

    @asyncio.coroutine
    def _async_query_state(self):
        """Query for state."""
        if not self._command_state:
            _LOGGER.error('No state command specified')
            return

        if self._value_template:
            ret = yield from CommandSwitch._async_query_state_value(
                self._command_state)
            return ret

        ret = yield from CommandSwitch._async_query_state_code(
            self._command_state)
        return ret

    @asyncio.coroutine
    def async_update(self):
        """Update device state."""
        if not self._command_state:
            return

        payload = str(yield from self._async_query_state())
        if not self._value_template:
            self._state = (payload.lower() == "true")

        payload = self._value_template.async_render_with_possible_json_value(
            payload)

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the device on."""
        ret = yield from CommandSwitch._switch(self._command_on)
        if (ret and not self._command_state):
            self._state = True
            self.update_ha_state()

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the device off."""
        ret = yield from CommandSwitch._switch(self._command_off)
        if (ret and not self._command_state):
            self._state = False
            self.update_ha_state()
