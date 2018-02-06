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

    add_devices([BLNETComponent(hass, id, blnet_id, comm)])


class BLNETComponent(Entity):
    """Implementation of a BL-NET - UVR1611 sensor and switch component."""

    def __init__(self, hass, id, blnet_id, communication):
        """Initialize the BL-NET sensor."""
        self.id = id
        self._blnet_id = blnet_id
        self.communication = communication
        self._name = blnet_id
        self._state = STATE_UNKNOWN
        self._unit_of_measurement = None
        self._icon = None

    @property
    def name(self):
        """Return the name of the sensor."""
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
    def unit_of_measurement(self):
        """Return the state of the device."""
        return self._unit_of_measurement
    
    def update(self):
        """Get the latest data from communication device """
        sensor_data = self.communication.data.get(self._blnet_id)
        
        if sensor_data is None:
            return
        
        self._name = sensor_data.get('friendly_name')
        self._state = sensor_data.get('value')
        self._unit_of_measurement = sensor_data.get('unit_of_measurement')
        self._icon = sensor_data.get('icon')

