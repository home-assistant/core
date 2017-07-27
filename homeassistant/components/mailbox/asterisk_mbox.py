"""
Asterisk Voicemail interface.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/mailbox.asteriskvm/
"""
import asyncio
import logging

from homeassistant.core import callback
from homeassistant.components.asterisk_mbox import DOMAIN
from homeassistant.components.mailbox import (Mailbox, CONTENT_TYPE_MPEG)
from homeassistant.helpers.dispatcher import (async_dispatcher_connect,
                                              async_dispatcher_send)

_LOGGER = logging.getLogger(__name__)

SIGNAL_MESSAGE_UPDATE = 'asterisk_mbox.message_updated'
SIGNAL_MESSAGE_REQUEST = 'asterisk_mbox.message_request'


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Asterix VM platform."""
    async_add_devices([AsteriskMailbox(hass)])


class AsteriskMailbox(Mailbox):
    """Asterisk VM Sensor."""

    def __init__(self, hass):
        """Initialize the sensor."""
        self._name = None
        self._attributes = None
        self._state = 0

    @property
    def name(self):
        """Return the name of the device."""
        return DOMAIN

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
    def get_media_type(self):
        """Return the supported media type."""
        return CONTENT_TYPE_MPEG

    def get_media(self, msgid):
        """Return the media blob for the msgid."""
        client = self.hass.data[DOMAIN].client
        return client.mp3(msgid, sync=True)

    def get_messages(self):
        """Return a list of the current messages."""
        return self.hass.data[DOMAIN].messages

    def delete(self, msgids):
        """Delete the specified messages."""
        client = self.hass.data[DOMAIN].client
        for sha in msgids:
            _LOGGER.info("Deleting: %s", sha)
            client.delete(sha)
        return True
