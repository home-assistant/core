"""
Support for LCN binary switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.lcn/
"""

import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_NAME
import homeassistant.helpers.config_validation as cv

from ..lcn import LcnDevice
from ..lcn.core import (
    CONF_ADDRESS, CONF_OUTPUT, OUTPUT_PORTS, RELAY_PORTS, is_address)

DEPENDENCIES = ['lcn']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_ADDRESS): is_address,
    vol.Required(CONF_OUTPUT): vol.Any(*(OUTPUT_PORTS + RELAY_PORTS)),
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the LCN switch platform."""
    device_id = config[CONF_NAME]
    if CONF_FRIENDLY_NAME not in config:
        config[CONF_FRIENDLY_NAME] = device_id

    output = config[CONF_OUTPUT]

    if output in OUTPUT_PORTS:
        device = LcnOutputSwitch(hass, config)
    elif output in RELAY_PORTS:
        device = LcnRelaySwitch(hass, config)

    async_add_entities([device])
    return True


class LcnOutputSwitch(LcnDevice, SwitchDevice):
    """Representation of a LCN switch for output ports."""

    def __init__(self, hass, config):
        """Initialize the LCN switch."""
        LcnDevice.__init__(self, hass, config)

        self.output = self.pypck.lcn_defs.OutputPort[
            config[CONF_OUTPUT].upper()]

        self._state = False

        self.hass.async_create_task(
            self.module_connection.activate_status_request_handler(
                self.output))

    @property
    def is_on(self):
        """Return True if entity is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self._state = True
        self.module_connection.dim_output(self.output.value, 100, 0)

        await self.async_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._state = False
        self.module_connection.dim_output(self.output.value, 0, 0)

        await self.async_update_ha_state()

    def module_input_received(self, input_obj):
        """Set switch state when LCN input object (command) is received."""
        if isinstance(input_obj, self.pypck.input.ModStatusOutput):
            if input_obj.get_output_id() == self.output.value:
                self._state = (input_obj.get_percent() > 0)

                self.async_schedule_update_ha_state()


class LcnRelaySwitch(LcnDevice, SwitchDevice):
    """Representation of a LCN switch for relay ports."""

    def __init__(self, hass, config):
        """Initialize the LCN switch."""
        LcnDevice.__init__(self, hass, config)

        self.output = self.pypck.lcn_defs.RelayPort[
            config[CONF_OUTPUT].upper()]

        self._state = False

        self.hass.async_create_task(
            self.module_connection.activate_status_request_handler(
                self.output))

    @property
    def is_on(self):
        """Return True if entity is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self._state = True

        states = [self.pypck.lcn_defs.RelayStateModifier.NOCHANGE] * 8
        states[self.output.value] = self.pypck.lcn_defs.RelayStateModifier.ON
        self.module_connection.control_relays(states)

        await self.async_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._state = False

        states = [self.pypck.lcn_defs.RelayStateModifier.NOCHANGE] * 8
        states[self.output.value] = self.pypck.lcn_defs.RelayStateModifier.OFF
        self.module_connection.control_relays(states)

        await self.async_update_ha_state()

    def module_input_received(self, input_obj):
        """Set switch state when LCN input object (command) is received."""
        if isinstance(input_obj, self.pypck.input.ModStatusRelays):
            self._state = input_obj.get_state(self.output.value)

            self.async_schedule_update_ha_state()
