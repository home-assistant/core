"""
Asterisk CDR interface.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/mailbox.asteriskvm/
"""
import asyncio
import logging
import hashlib
import datetime

from homeassistant.core import callback
from homeassistant.components.asterisk_mbox import SIGNAL_CDR_UPDATE
from homeassistant.components.asterisk_mbox import DOMAIN as MBOX_DOMAIN
from homeassistant.components.mailbox import Mailbox
from homeassistant.helpers.dispatcher import async_dispatcher_connect

DEPENDENCIES = ['asterisk_mbox']
_LOGGER = logging.getLogger(__name__)
DOMAIN = "asterisk_cdr"


@asyncio.coroutine
def async_get_handler(hass, config, async_add_devices, discovery_info=None):
    """Set up the Asterix CDR platform."""
    return AsteriskCDR(hass, DOMAIN)


class AsteriskCDR(Mailbox):
    """Asterisk VM Call Data Record mailbox."""

    def __init__(self, hass, name):
        """Initialie Asterisk CDR."""
        super().__init__(hass, name)
        self.cdr = []
        async_dispatcher_connect(
            self.hass, SIGNAL_CDR_UPDATE, self._update_callback)

    @callback
    def _update_callback(self, msg):
        """Update the message count in HA, if needed."""
        cdr = []
        for entry in self.hass.data[MBOX_DOMAIN].cdr:
            timestamp = datetime.datetime.strptime(
                entry['time'], "%Y-%m-%d %H:%M:%S").timestamp()
            info = {
                'origtime': timestamp,
                'callerid': entry['callerid'],
                'duration': entry['duration'],
            }
            sha = hashlib.sha256(str(entry).encode('utf-8')).hexdigest()
            msg = "Destination: {}\nApplication: {}\n Context: {}".format(
                entry['dest'], entry['application'], entry['context'])
            cdr.append({'info': info, 'sha': sha, 'text': msg})
        self.cdr = cdr
        self.async_update()

    @asyncio.coroutine
    def async_get_messages(self):
        """Return a list of the current messages."""
        return self.cdr
