"""
Support for switches managed by a LifeSOS alarm / automation system.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.lifesos/
"""
import logging

from homeassistant.components.lifesos import (
    LifeSOSDevice, DATA_BASEUNIT, SIGNAL_PROPERTIES_CHANGED,
    SIGNAL_SWITCH_STATE_CHANGED)
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import CONF_NAME, CONF_SWITCHES
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['lifesos']


async def async_setup_platform(
        hass, config, async_add_devices, discovery_info=None):
    """Set up the LifeSOS switches."""
    from lifesospy.enums import SwitchNumber

    devices = []
    for num in discovery_info[CONF_SWITCHES]:
        try:
            switch_number = list(SwitchNumber)[num - 1]
        except IndexError:
            _LOGGER.error("Switch number %s is outside valid range", num)
            continue
        device = LifeSOSSwitch(
            hass.data[DATA_BASEUNIT],
            discovery_info[CONF_NAME],
            switch_number)
        devices.append(device)
    if devices:
        async_add_devices(devices)


class LifeSOSSwitch(LifeSOSDevice, SwitchDevice):
    """Representation of a LifeSOS switch."""

    def __init__(self, baseunit, name, switch_number):
        switch_name = "{0} {1}".format(
            name, switch_number.name)
        super().__init__(baseunit, switch_name)

        self._switch_number = switch_number
        self._is_on = False

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on

    @property
    def available(self):
        """Return True if device is available."""
        return self._baseunit.is_connected

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_PROPERTIES_CHANGED,
            self.handle_properties_changed)
        async_dispatcher_connect(
            self.hass, SIGNAL_SWITCH_STATE_CHANGED,
            self.handle_switch_state_changed)

    @callback
    def handle_properties_changed(self, changes):
        """When the base unit connection state changes, update availability."""
        from lifesospy.baseunit import BaseUnit

        # Base unit connection state determines whether we are available
        do_update = False
        for change in changes:
            if change.name == BaseUnit.PROP_IS_CONNECTED:
                do_update = True
        if do_update:
            self.async_schedule_update_ha_state()

    @callback
    def handle_switch_state_changed(self, switch_number, state):
        """When the switch state changes, notify HA"""
        if switch_number != self._switch_number:
            return
        self._is_on = state
        self.async_schedule_update_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self._baseunit.async_set_switch_state(
            self._switch_number, True)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self._baseunit.async_set_switch_state(
            self._switch_number, False)
