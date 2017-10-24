"""Support for Asterisk Voicemail interface."""

import logging

import voluptuous as vol


import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.const import (CONF_HOST,
                                 CONF_PORT, CONF_PASSWORD)

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import (async_dispatcher_connect,
                                              async_dispatcher_send)

REQUIREMENTS = ['asterisk_mbox==0.4.0']

SIGNAL_MESSAGE_UPDATE = 'asterisk_mbox.message_updated'
SIGNAL_MESSAGE_REQUEST = 'asterisk_mbox.message_request'

DOMAIN = 'asterisk_mbox'

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): int,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up for the Asterisk Voicemail box."""
    conf = config.get(DOMAIN)

    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)
    password = conf.get(CONF_PASSWORD)

    hass.data[DOMAIN] = AsteriskData(hass, host, port, password)

    discovery.load_platform(hass, "mailbox", DOMAIN, {}, config)

    return True


class AsteriskData(object):
    """Store Asterisk mailbox data."""

    def __init__(self, hass, host, port, password):
        """Init the Asterisk data object."""
        from asterisk_mbox import Client as asteriskClient

        self.hass = hass
        self.client = asteriskClient(host, port, password, self.handle_data)
        self.messages = []

        async_dispatcher_connect(
            self.hass, SIGNAL_MESSAGE_REQUEST, self._request_messages)

    @callback
    def handle_data(self, command, msg):
        """Handle changes to the mailbox."""
        from asterisk_mbox.commands import CMD_MESSAGE_LIST

        if command == CMD_MESSAGE_LIST:
            _LOGGER.info("AsteriskVM sent updated message list")
            self.messages = sorted(msg,
                                   key=lambda item: item['info']['origtime'],
                                   reverse=True)
            async_dispatcher_send(self.hass, SIGNAL_MESSAGE_UPDATE,
                                  self.messages)

    @callback
    def _request_messages(self):
        """Handle changes to the mailbox."""
        _LOGGER.info("Requesting message list")
        self.client.messages()
