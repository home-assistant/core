"""
Support for Freebox devices (Freebox v6 and Freebox mini 4K).

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch/freebox/
"""
import logging

from homeassistant.components.freebox import DATA_FREEBOX
from homeassistant.const import (STATE_OFF, STATE_ON)
from homeassistant.helpers.entity import ToggleEntity

DEPENDENCIES = ['freebox']

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, add_entities, discovery_info=None):
    """Set up the sensors."""
    fbx = hass.data[DATA_FREEBOX]
    add_entities([
        FbxWifiSwitch(fbx),
    ])


class FbxWifiSwitch(ToggleEntity):
    """Representation of a freebox wifi switch."""

    def __init__(self, fbx):
        """Initilize the Wifi switch."""
        self._name = 'Freebox WiFi'
        self._state = STATE_OFF
        self.fbx = fbx
        self.wifi_config = {}

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def state(self):
        """Return the state of the switch."""
        return self._state

    @property
    def should_poll(self):
        """Poll for status."""
        return True

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state == STATE_ON

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        self.wifi_config = {"enabled": True}
        await self.fbx.wifi.set_global_config(self.wifi_config)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        self.wifi_config = {"enabled": False}
        await self.fbx.wifi.set_global_config(self.wifi_config)

    async def async_update(self):
        """Get the state and update it."""
        datas = await self.fbx.wifi.get_global_config()
        active = datas['enabled']
        self._state = STATE_ON if active else STATE_OFF
