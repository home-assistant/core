"""
Connect to a BL-NET via it's web interface and read and write data
TODO: as component
"""
import logging

import voluptuous as vol
from pyblnet import BLNET, test_blnet
import asyncio

from homeassistant.const import (
    CONF_RESOURCE, STATE_UNKNOWN, CONF_PASSWORD)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import SwitchDevice

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'blnet'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the BLNET component"""

    if discovery_info is None:
        _LOGGER.error("No BL-Net communication configured")
        return False
    
    id = discovery_info['id']
    blnet_id = discovery_info['ent_id']
    comm = hass.data[DOMAIN + '_data']

    add_devices([BLNETSwitch(hass, id, blnet_id, comm)])


class BLNETSwitch(SwitchDevice):
    """Representation of a switch that toggles a digital output of the UVR1611."""

    def __init__(self, name, id, blnet_id, comm):
        """Initialize the MQTT switch."""
        self._blnet_id = blnet_id
        self._id = id
        self.communication = comm
        self._name = blnet_id
        self._state = False
        self._state = STATE_UNKNOWN
        self._icon = None
        self._mode = STATE_UNKNOWN

    def update(self):
        """Get the latest data from communication device """
        sensor_data = self.communication.data.get(self._blnet_id)
        
        if sensor_data is None:
            return
        
        self._name = sensor_data.get('friendly_name')
        if sensor_data.get('value') == 'EIN':
            self._state = 'on'
        # Nonautomated switch, toggled off => switch off
        else:
            self._state = 'off'
        self._icon = sensor_data.get('icon')
        self._mode = sensor_data.get('mode')


    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state
    
    @property
    def icon(self):
        """Return the state of the device."""
        return self._icon
    
    @property
    def mode(self):
        """Return the state of the device."""
        return self._mode

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on.
        """
        self.communication.turn_on(self._id)

    def turn_off(self, **kwargs):
        """Turn the device off.
        """
        self.communication.turn_off(self._id)
