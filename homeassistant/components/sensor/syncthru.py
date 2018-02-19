"""
Connect to a Samsung Printer via it's SyncThru
 web interface and read data
"""
import logging

REQUIREMENTS = [
    'pysyncthru>=0.1.3'
    ]


import voluptuous as vol
import asyncio

from homeassistant.const import (
    CONF_RESOURCE, STATE_UNKNOWN, CONF_HOST, CONF_NAME, CONF_FRIENDLY_NAME)
from homeassistant.components.discovery import SERVICE_SAMSUNG_PRINTER
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Samsung Printer'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCE): cv.url
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the BLNET component"""

    from pysyncthru import SyncThru, test_syncthru

    if discovery_info is not None:
        host = discovery_info.get(CONF_HOST)
        name = discovery_info.get(CONF_NAME, DEFAULT_NAME)
    else:
        host = config.get(CONF_RESOURCE)
        name = config.get(CONF_NAME, DEFAULT_NAME)
        
    _LOGGER.error("Discovered a new Samsung Printer: {}".format(discovery_info))

    if test_syncthru(host) is False:
        _LOGGER.error("No SyncThru Printer reached under given resource")
        return False
    
    sync_comp = SyncThruSensor(hass, SyncThru(host), name)
    
    add_devices([sync_comp], True)

    return True
    


class SyncThruSensor(Entity):
    """Implementation of a Samsung Printer sensor platform."""

    def __init__(self, hass, syncthru, name):
        """Initialize the BL-NET sensor."""
        self._hass = hass
        self.syncthru = syncthru
        # init the devices entitiy name starting without number/name
        self._attributes = {}
        self._state = STATE_UNKNOWN
        self._name = name
        self._icon = 'mdi:printer'

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

    def update(self):
        """Get the latest data from SyncThru and update the state."""
        syncthru = self.syncthru

        syncthru.update()
        self._state = syncthru.deviceStatus()
        
        if syncthru.isOnline():
            self._friendly_name = syncthru.model()
            self._attributes[CONF_FRIENDLY_NAME] = self._friendly_name

            self._attributes['output_tray'] = syncthru.outputTrayStatus()
            for key, value in syncthru.systemStatus().items():
                self._attributes[str(key)] = value
            for key, value in syncthru.tonerStatus().items():
                self._attributes['toner_' + str(key)] = value
            for key, value in syncthru.drumStatus().items():
                self._attributes['drum_' + str(key)] = value
            for key, value in syncthru.inputTrayStatus().items():
                self._attributes['input_tray_' + str(key)] = value

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._attributes
