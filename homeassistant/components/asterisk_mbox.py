"""Support for Asterisk Voicemail interface."""

import asyncio
import logging
from contextlib import suppress

import async_timeout
import voluptuous as vol


from aiohttp import web

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.const import (CONF_HOST,
                                 CONF_PORT, CONF_PASSWORD)

from homeassistant.const import (HTTP_BAD_REQUEST,
                                 HTTP_NOT_FOUND)

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import (async_dispatcher_connect,
                                              async_dispatcher_send)

from homeassistant.components.http import HomeAssistantView

REQUIREMENTS = ['asterisk_mbox==0.4.0']
DEPENDENCIES = ['http']

CONTENT_TYPE_MPEG = 'audio/mpeg'
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

    discovery.load_platform(hass, "sensor", DOMAIN, {}, config)

    hass.components.frontend.register_built_in_panel(
        'mailbox', 'Mailbox', 'mdi:account-location')
    hass.http.register_view(AsteriskMboxMsgView())
    hass.http.register_view(AsteriskMboxMP3View())
    hass.http.register_view(AsteriskMboxDeleteView())

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


class AsteriskMboxMsgView(HomeAssistantView):
    """View to return the list of messages."""

    url = "/api/asteriskmbox/messages"
    name = "api:asteriskmbox:messages"

    @asyncio.coroutine
    def get(self, request):
        """Retrieve Asterisk messages."""
        hass = request.app['hass']
        msgs = hass.data[DOMAIN].messages
        _LOGGER.info("Sending: %s", msgs)
        return self.json(msgs)


class AsteriskMboxDeleteView(HomeAssistantView):
    """View to delete selected messages."""

    url = "/api/asteriskmbox/delete"
    name = "api:asteriskmbox:delete"

    @asyncio.coroutine
    def post(self, request):
        """Delete items."""
        try:
            data = yield from request.json()

            hass = request.app['hass']
            client = hass.data[DOMAIN].client
            for sha in data:
                _LOGGER.info("Deleting: %s", sha)
                client.delete(sha)
        except ValueError:
            return self.json_message('Bad item id', HTTP_BAD_REQUEST)


class AsteriskMboxMP3View(HomeAssistantView):
    """View to return an MP3."""

    url = r"/api/asteriskmbox/mp3/{sha:[0-9a-f]+}"
    name = "api:asteriskmbox:mp3"

    @asyncio.coroutine
    def get(self, request, sha):
        """Retrieve Asterisk mp3."""
        _LOGGER.info("Sending mp3 for %s", sha)

        hass = request.app['hass']
        client = hass.data[DOMAIN].client

        def fetch():
            """Read MP3 from server."""
            from asterisk_mbox import ServerError

            try:
                return client.mp3(sha, sync=True)
            except ServerError as err:
                _LOGGER.error("Error getting MP3: %s", err)
                return self.json_message(err, HTTP_NOT_FOUND)

        with suppress(asyncio.CancelledError, asyncio.TimeoutError):
            with async_timeout.timeout(10, loop=request.app['hass'].loop):
                stream = yield from hass.async_add_job(fetch)

            if stream:
                return web.Response(body=stream,
                                    content_type=CONTENT_TYPE_MPEG)

        return web.Response(status=500)
