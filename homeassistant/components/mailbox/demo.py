"""
Asterisk Voicemail interface.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/mailbox.asteriskvm/
"""
import asyncio
import logging
import os
from hashlib import sha1

from homeassistant.util import dt

from homeassistant.components.mailbox import (Mailbox, CONTENT_TYPE_MPEG,
                                              StreamError)

_LOGGER = logging.getLogger(__name__)
DOMAIN = "DemoMailbox"


@asyncio.coroutine
def async_get_handler(hass, config, discovery_info=None):
    """Set up the Demo mailbox."""
    return DemoMailbox(hass, DOMAIN)


class DemoMailbox(Mailbox):
    """Demo Mailbox."""

    def __init__(self, hass, name):
        """Initialize Demo mailbox."""
        super().__init__(hass, name)
        self._messages = {}
        txt = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
        for idx in range(0, 10):
            msgtime = int(dt.as_timestamp(
                dt.utcnow()) - 3600 * 24 * (10 - idx))
            msgtxt = "Message {}. {}".format(
                idx + 1, txt * (1 + idx * (idx % 2)))
            msgsha = sha1(msgtxt.encode('utf-8')).hexdigest()
            msg = {"info": {"origtime": msgtime,
                            "callerid": "John Doe <212-555-1212>",
                            "duration": "10"},
                   "text": msgtxt,
                   "sha":  msgsha}
            self._messages[msgsha] = msg

    @property
    def media_type(self):
        """Return the supported media type."""
        return CONTENT_TYPE_MPEG

    @asyncio.coroutine
    def async_get_media(self, msgid):
        """Return the media blob for the msgid."""
        if msgid not in self._messages:
            raise StreamError("Message not found")

        audio_path = os.path.join(
            os.path.dirname(__file__), '..', 'tts', 'demo.mp3')
        with open(audio_path, 'rb') as file:
            return file.read()

    @asyncio.coroutine
    def async_get_messages(self):
        """Return a list of the current messages."""
        return sorted(self._messages.values(),
                      key=lambda item: item['info']['origtime'],
                      reverse=True)

    def async_delete(self, msgid):
        """Delete the specified messages."""
        if msgid in self._messages:
            _LOGGER.info("Deleting: %s", msgid)
            del self._messages[msgid]
        self.async_update()
        return True
