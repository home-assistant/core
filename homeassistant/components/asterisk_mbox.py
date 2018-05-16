"""
Support for Asterisk Voicemail interface.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/asterisk_mbox/
"""
import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)

REQUIREMENTS = ['asterisk_mbox==0.4.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'asterisk_mbox'

SIGNAL_MESSAGE_REQUEST = 'asterisk_mbox.message_request'
SIGNAL_MESSAGE_UPDATE = 'asterisk_mbox.message_updated'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_PORT): int,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up for the Asterisk Voicemail box."""
    conf = config.get(DOMAIN)

    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)
    password = conf.get(CONF_PASSWORD)

    hass.data[DOMAIN] = AsteriskData(hass, host, port, password)

    discovery.load_platform(hass, 'mailbox', DOMAIN, {}, config)

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
            _LOGGER.debug("AsteriskVM sent updated message list")
            self.messages = sorted(
                msg, key=lambda item: item['info']['origtime'], reverse=True)
            async_dispatcher_send(
                self.hass, SIGNAL_MESSAGE_UPDATE, self.messages)

    @callback
    def _request_messages(self):
        """Handle changes to the mailbox."""
        _LOGGER.debug("Requesting message list")
        self.client.messages()
