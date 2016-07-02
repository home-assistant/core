"""
Support for Autohub lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.autohub/
"""
import time
import logging

from homeassistant.components.autohub import AUTOHUBWS

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_EFFECT, ATTR_RGB_COLOR, Light)
from homeassistant.loader import get_component

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Autohub Hub light platform."""
    devs = []
    device_address, device_name = discovery_info
    device = AUTOHUBWS.getDeviceFromAddress(device_address)
    devs.append(AutohubToggleDevice(device))
    add_devices(devs)
    return

    

class AutohubToggleDevice(Light):
    """An abstract Class for an Autohub node."""

    def __init__(self, node):
        """Initialize the device."""
        self.node = node
        self.insight_params = None
        self.maker_params = None
        self._state = None
        self.light_id = node.device_address_
		
        self._value = self.node._properties_.get("light_status", 0)
        self.node.on_device_update(self._update_callback)

    def _update_callback(self):
        """Called by the Wemo device callback to update state."""
        _LOGGER.info(
            'Subscription update for  %s',
            self.node.device_address_)
        if not hasattr(self, 'hass'):
            self.update()
            return
        self.update_ha_state(True)

    @property
    def unique_id(self):
        """Return the ID of this autohub node."""
        return self.node.device_address_

    @property
    def name(self):
        """Return the the name of the node."""
        return self.node.device_name_

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self.node._properties_.get('light_status', 0)

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        return self.node._properties_.get('light_status', 0) != 0

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False

    def turn_on(self, **kwargs):
        """Turn device on."""
        level = self.node._properties_.get("button_on_level", 255)

        if ATTR_BRIGHTNESS in kwargs:
            level = kwargs[ATTR_BRIGHTNESS]

        self._value = level
        self.node._properties_["light_status"] = self._value
        self.node.send_command('on', level)
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """Turn device off."""
        self._value = 0
        self.node._properties_["light_status"] = self._value
        self.node.send_command('off')
        self.update_ha_state()

    def update(self):
        """Update state of the sensor."""
        #resp = self.node.send_command('status', wait=False)
        #try:
            #print(resp)
        #self.node.reload_details()
        self._value = self.node._properties_.get("light_status", 0)
        #except KeyError:
            #pass
