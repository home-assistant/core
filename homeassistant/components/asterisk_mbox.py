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
from homeassistant.helpers.dispatcher import (async_dispatcher_connect,
                                              dispatcher_send)

REQUIREMENTS = ['asterisk_mbox==0.5.0']

_LOGGER = logging.getLogger(__name__)

SIGNAL_DISCOVER_PLATFORM = "asterisk_mbox.discover_platform"
SIGNAL_MESSAGE_UPDATE = 'asterisk_mbox.message_updated'
SIGNAL_MESSAGE_REQUEST = 'asterisk_mbox.message_request'
SIGNAL_CDR_UPDATE = 'asterisk_mbox.message_updated'
SIGNAL_CDR_REQUEST = 'asterisk_mbox.message_request'

DOMAIN = 'asterisk_mbox'

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

    hass.data[DOMAIN] = AsteriskData(host, port, password, config)

    return True


class AsteriskData(object):
    """Store Asterisk mailbox data."""

    def __init__(self,host, port, password, config):
        """Init the Asterisk data object."""
        from asterisk_mbox import Client as asteriskClient

        self.config = config
        self.client = asteriskClient(host, port, password, self.handle_data)
        self.messages = None
        self.cdr = None

    async def async_added_to_hass(self):
      """Init Callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_MESSAGE_REQUEST, self._request_messages)
        async_dispatcher_connect(
            self.hass, SIGNAL_CDR_REQUEST, self._request_cdr)
        async_dispatcher_connect(
            self.hass, SIGNAL_DISCOVER_PLATFORM, self._discover_platform)

    @callback
    def _discover_platform(self, component):
        self.hass.async_add_job(discovery.async_load_platform(
            self.hass, "mailbox", component, {}, self.config))

    def handle_data(self, command, msg):
        """Handle changes to the mailbox."""
        from asterisk_mbox.commands import (CMD_MESSAGE_LIST,
                                            CMD_MESSAGE_CDR_AVAILABLE,
                                            CMD_MESSAGE_CDR)

        if command == CMD_MESSAGE_LIST:
            _LOGGER.debug("AsteriskVM sent updated message list")
            old_messages = self.messages
            self.messages = sorted(
                msg, key=lambda item: item['info']['origtime'], reverse=True)

            if not isinstance(old_messages, list):
                dispatcher_send(self.hass, SIGNAL_DISCOVER_PLATFORM,
                                DOMAIN)
            dispatcher_send(self.hass, SIGNAL_MESSAGE_UPDATE, self.messages)
        elif command == CMD_MESSAGE_CDR:
            _LOGGER.info("AsteriskVM sent updated CDR list")
            self.cdr = msg['entries']
            dispatcher_send(self.hass, SIGNAL_CDR_UPDATE, self.cdr)
        elif command == CMD_MESSAGE_CDR_AVAILABLE:
            if not isinstance(self.cdr, list):
                self.cdr = []
                dispatcher_send(self.hass, SIGNAL_DISCOVER_PLATFORM,
                                "asterisk_cdr")
            dispatcher_send(self.hass, SIGNAL_CDR_REQUEST)

    @callback
    def _request_messages(self):
        """Handle changes to the mailbox."""
        _LOGGER.debug("Requesting message list")
        self.client.messages()

    @callback
    def _request_cdr(self):
        """Handle changes to the CDR."""
        _LOGGER.debug("Requesting CDR list")
        self.client.get_cdr()
