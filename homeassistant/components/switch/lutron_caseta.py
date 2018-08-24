"""
Support for Lutron Caseta switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sitch.lutron_caseta/
"""
import asyncio
import logging

from homeassistant.components.lutron_caseta import (
    LUTRON_CASETA_SMARTBRIDGE, LutronCasetaDevice)
from homeassistant.components.switch import SwitchDevice, DOMAIN

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['lutron_caseta']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities,
                         discovery_info=None):
    """Set up Lutron switch."""
    devs = []
    bridge = hass.data[LUTRON_CASETA_SMARTBRIDGE]
    switch_devices = bridge.get_devices_by_domain(DOMAIN)

    for switch_device in switch_devices:
        dev = LutronCasetaLight(switch_device, bridge)
        devs.append(dev)

    async_add_entities(devs, True)
    return True


class LutronCasetaLight(LutronCasetaDevice, SwitchDevice):
    """Representation of a Lutron Caseta switch."""

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        self._smartbridge.turn_on(self._device_id)

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        self._smartbridge.turn_off(self._device_id)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state["current_state"] > 0

    @asyncio.coroutine
    def async_update(self):
        """Update when forcing a refresh of the device."""
        self._state = self._smartbridge.get_device_by_id(self._device_id)
        _LOGGER.debug(self._state)
