"""
Sensor for Asterisk Voicemail box.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.asteriskvm/
"""
import asyncio
import logging


from homeassistant.helpers.entity import Entity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import (async_dispatcher_connect,
                                              async_dispatcher_send)

_LOGGER = logging.getLogger(__name__)

SIGNAL_MESSAGE_UPDATE = 'asterisk_mbox.message_updated'
SIGNAL_MESSAGE_REQUEST = 'asterisk_mbox.message_request'
DOMAIN = 'Voicemail'


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Asterix VM platform."""
    async_add_devices([AsteriskVMSensor(hass)])


class AsteriskVMSensor(Entity):
    """Asterisk VM Sensor."""

    def __init__(self, hass):
        """Initialize the sensor."""
        self._name = None
        self._attributes = None
        self._state = 0

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_MESSAGE_UPDATE, self._update_callback)
        async_dispatcher_send(self.hass, SIGNAL_MESSAGE_REQUEST)

    @callback
    def _update_callback(self, msg):
        """Update the message count in HA, if needed."""
        self._state = len(msg)
        _LOGGER.info("Update Callback")
        self.hass.async_add_job(self.async_update_ha_state(True))

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{}'.format(self._name or DOMAIN)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state
