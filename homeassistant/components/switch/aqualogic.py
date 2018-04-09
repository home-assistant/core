"""
Support for AquaLogic switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.aqualogic/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.components.aqualogic as aqualogic
from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, ATTR_ATTRIBUTION)
from aqualogic.core import AquaLogic, Keys, Leds

DEPENDENCIES = ['aqualogic']

_LOGGER = logging.getLogger(__name__)

SWITCH_TYPES = {
    'lights': ['Lights', Keys.LIGHTS, Leds.LIGHTS],
    'filter': ['Filter', Keys.FILTER, Leds.FILTER],
    'aux_1': ['Aux 1', Keys.AUX_1, Leds.AUX_1],
    'aux_2': ['Aux 2', Keys.AUX_2, Leds.AUX_2],
    'aux_3': ['Aux 3', Keys.AUX_3, Leds.AUX_3],
    'aux_4': ['Aux 4', Keys.AUX_4, Leds.AUX_4],
    'aux_5': ['Aux 5', Keys.AUX_5, Leds.AUX_5],
    'aux_6': ['Aux 6', Keys.AUX_6, Leds.AUX_6],
    'aux_7': ['Aux 7', Keys.AUX_7, Leds.AUX_7],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SWITCH_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SWITCH_TYPES)]),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the switch platform."""
    switches = []

    component = hass.data[aqualogic.DOMAIN]
    for switch_type in config.get(CONF_MONITORED_CONDITIONS):
        switches.append(AquaLogicSwitch(component, switch_type))

    async_add_devices(switches)


class AquaLogicSwitch(SwitchDevice):
    """Switch implementation for the AquaLogic component."""

    def __init__(self, component, switch_type):
        """Initialize switch."""
        self._component = component
        self._type = switch_type
        self._state = False
        self.update()

    @property
    def name(self):
        return "AquaLogic {}".format(SWITCH_TYPES[self._type][0])

    def update(self):
        """Update device state."""
        panel = self._component.panel
        if panel == None:
            return
        self._state = panel.is_led_enabled(SWITCH_TYPES[self._type][2])
        _LOGGER.error("update %d", self._state)

    @property
    def is_on(self):
        """Return true if device is on."""
        _LOGGER.error("is_on %d", self._state)
        return self._state

    def turn_on(self):
        """Turn the device on."""
        if self.is_on:
            return
        _LOGGER.error("turn_on")
        panel = self._component.panel
        if panel == None:
            return
        panel.queue_key(SWITCH_TYPES[self._type][1])
        self._state = True
        
    def turn_off(self):
        """Turn the device off."""
        if not self.is_on:
            return
        _LOGGER.error("turn_off")
        panel = self._component.panel
        if panel == None:
            return
        panel.queue_key(SWITCH_TYPES[self._type][1])
        self._state = False
