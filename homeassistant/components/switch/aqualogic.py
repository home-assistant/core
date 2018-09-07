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

DEPENDENCIES = ['aqualogic']

_LOGGER = logging.getLogger(__name__)

SWITCH_TYPES = {
    'lights': 'Lights',
    'filter': 'Filter',
    'filter_low_speed': 'Filter Low Speed',
    'aux_1': 'Aux 1',
    'aux_2': 'Aux 2',
    'aux_3': 'Aux 3',
    'aux_4': 'Aux 4',
    'aux_5': 'Aux 5',
    'aux_6': 'Aux 6',
    'aux_7': 'Aux 7',
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
        from aqualogic.core import AquaLogic, States
        import aqualogic.core
        print(aqualogic.core.__file__)
        self._component = component
        self._type = switch_type
        self._stateName = {
            'lights': States.LIGHTS,
            'filter': States.FILTER,
            'filter_low_speed': States.FILTER_LOW_SPEED,
            'aux_1': States.AUX_1,
            'aux_2': States.AUX_2,
            'aux_3': States.AUX_3,
            'aux_4': States.AUX_4,
            'aux_5': States.AUX_5,
            'aux_6': States.AUX_6,
            'aux_7': States.AUX_7
        }[switch_type]

    @property
    def name(self):
        return "AquaLogic {}".format(SWITCH_TYPES[self._type])

    @property
    def is_on(self):
        """Return true if device is on."""
        panel = self._component.panel
        if panel == None:
            return False
        state = panel.get_state(self._stateName);
        print(self.name + " "  + str(state));
        print('States: {}'.format(panel.states()))
        return state

    def turn_on(self):
        """Turn the device on."""
        if self.is_on:
            return
        panel = self._component.panel
        if panel == None:
            return
        panel.set_state(self._stateName, True)
        
    def turn_off(self):
        """Turn the device off."""
        if not self.is_on:
            return
        panel = self._component.panel
        if panel == None:
            return
        panel.set_state(self._stateName, False)
