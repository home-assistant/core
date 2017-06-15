"""
Support for AlarmDecoder Sensors (Shows Panel Display).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.alarmdecoder/
"""
import asyncio
import logging

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.components.alarmdecoder import (SIGNAL_PANEL_MESSAGE)
from homeassistant.const import (STATE_UNKNOWN)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['alarmdecoder']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up for AlarmDecoder sensor devices."""
    _LOGGER.debug("AlarmDecoderSensor: async_setup_platform")

    device = AlarmDecoderSensor(hass)

    async_add_devices([device])


class AlarmDecoderSensor(Entity):
    """Representation of an AlarmDecoder keypad."""

    def __init__(self, hass):
        """Initialize the alarm panel."""
        self._display = ""
        self._state = STATE_UNKNOWN
        self._icon = 'mdi:alarm-check'
        self._name = 'Alarm Panel Display'

        _LOGGER.debug("Setting up panel")

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_PANEL_MESSAGE, self._message_callback)

    @callback
    def _message_callback(self, message):
        if self._display != message.text:
            self._display = message.text
            self.hass.async_add_job(self.async_update_ha_state())

    @property
    def icon(self):
        """Return the icon if any."""
        return self._icon

    @property
    def state(self):
        """Return the overall state."""
        return self._display

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False
