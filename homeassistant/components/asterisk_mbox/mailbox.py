"""Support for the Asterisk Voicemail interface."""
import logging

from homeassistant.components.mailbox import (
    CONTENT_TYPE_MPEG, Mailbox, StreamError)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN as ASTERISK_DOMAIN

_LOGGER = logging.getLogger(__name__)

SIGNAL_MESSAGE_REQUEST = 'asterisk_mbox.message_request'
SIGNAL_MESSAGE_UPDATE = 'asterisk_mbox.message_updated'


async def async_get_handler(hass, config, discovery_info=None):
    """Set up the Asterix VM platform."""
    return AsteriskMailbox(hass, ASTERISK_DOMAIN)


class AsteriskMailbox(Mailbox):
    """Asterisk VM Sensor."""

    def __init__(self, hass, name):
        """Initialize Asterisk mailbox."""
        super().__init__(hass, name)
        async_dispatcher_connect(
            self.hass, SIGNAL_MESSAGE_UPDATE, self._update_callback)

    @callback
    def _update_callback(self, msg):
        """Update the message count in HA, if needed."""
        self.async_update()

    @property
    def media_type(self):
        """Return the supported media type."""
        return CONTENT_TYPE_MPEG

    @property
    def can_delete(self):
        """Return if messages can be deleted."""
        return True

    @property
    def has_media(self):
        """Return if messages have attached media files."""
        return True

    async def async_get_media(self, msgid):
        """Return the media blob for the msgid."""
        from asterisk_mbox import ServerError
        client = self.hass.data[ASTERISK_DOMAIN].client
        try:
            return client.mp3(msgid, sync=True)
        except ServerError as err:
            raise StreamError(err)

    async def async_get_messages(self):
        """Return a list of the current messages."""
        return self.hass.data[ASTERISK_DOMAIN].messages

    def async_delete(self, msgid):
        """Delete the specified messages."""
        client = self.hass.data[ASTERISK_DOMAIN].client
        _LOGGER.info("Deleting: %s", msgid)
        client.delete(msgid)
        return True
