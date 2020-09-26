"""Support for the Asterisk CDR interface."""
import datetime
import hashlib
import logging

from homeassistant.components.asterisk_mbox import (
    DOMAIN as ASTERISK_DOMAIN,
    SIGNAL_CDR_UPDATE,
)
from homeassistant.components.mailbox import Mailbox
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)

MAILBOX_NAME = "asterisk_cdr"


async def async_get_handler(hass, config, discovery_info=None):
    """Set up the Asterix CDR platform."""
    return AsteriskCDR(hass, MAILBOX_NAME)


class AsteriskCDR(Mailbox):
    """Asterisk VM Call Data Record mailbox."""

    def __init__(self, hass, name):
        """Initialize Asterisk CDR."""
        super().__init__(hass, name)
        self.cdr = []
        async_dispatcher_connect(self.hass, SIGNAL_CDR_UPDATE, self._update_callback)

    @callback
    def _update_callback(self, msg):
        """Update the message count in HA, if needed."""
        self._build_message()
        self.async_update()

    def _build_message(self):
        """Build message structure."""
        cdr = []
        for entry in self.hass.data[ASTERISK_DOMAIN].cdr:
            timestamp = datetime.datetime.strptime(
                entry["time"], "%Y-%m-%d %H:%M:%S"
            ).timestamp()
            info = {
                "origtime": timestamp,
                "callerid": entry["callerid"],
                "duration": entry["duration"],
            }
            sha = hashlib.sha256(str(entry).encode("utf-8")).hexdigest()
            msg = (
                f"Destination: {entry['dest']}\n"
                f"Application: {entry['application']}\n "
                f"Context: {entry['context']}"
            )
            cdr.append({"info": info, "sha": sha, "text": msg})
        self.cdr = cdr

    async def async_get_messages(self):
        """Return a list of the current messages."""
        if not self.cdr:
            self._build_message()
        return self.cdr
