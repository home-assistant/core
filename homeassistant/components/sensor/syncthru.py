"""
Connect to a Samsung Printer via it's SyncThru
 web interface and read data
"""
import logging

REQUIREMENTS = [
    'pysyncthru>=0.1.2'
    ]


import voluptuous as vol
import asyncio

from homeassistant.const import (
    CONF_RESOURCE, STATE_UNKNOWN, CONF_PASSWORD)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)

FRIENDLY_NAME = 'friendly_name'


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCE): cv.url
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the BLNET component"""

    from pysyncthru import SyncThru, test_syncthru

    resource = config.get(CONF_RESOURCE)

    if test_syncthru(resource) is None:
        _LOGGER.error("No SyncThru Printer reached under given resource")
        return False

    sync_comp = SyncThruSensor(hass, SyncThru(resource))
    add_devices([sync_comp], True)


class SyncThruSensor(Entity):
    """Implementation of a Samsung Printer sensor platform."""

    def __init__(self, hass, syncthru):
        """Initialize the BL-NET sensor."""
        self._hass = hass
        self.syncthru = syncthru
        # init the devices entitiy name starting without number/name
        self._attributes = {}
        self._state = STATE_UNKNOWN
        self._name = 'SyncThru Printer'
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
        self._friendly_name = syncthru.model()

        self._attributes['output_tray'] = syncthru.outputTrayStatus()
        for key, value in syncthru.systemStatus().items():
            self._attributes[key] = value
        for key, value in syncthru.tonerStatus().items():
            self._attributes['toner_' + key] = value
        for key, value in syncthru.drumStatus().items():
            self._attributes['drum_' + key] = value
        for key, value in syncthru.inputTrayStatus().items():
            self._attributes['input_tray_' + key] = value

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""

        self._attributes[FRIENDLY_NAME] = self._friendly_name
        return self._attributes
