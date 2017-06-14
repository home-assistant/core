"""
Exposes regular REST commands as services.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/hassio/
"""
import asyncio
import logging
import os
import re

import aiohttp
from aiohttp import web
from aiohttp.web_exceptions import HTTPBadGateway
from aiohttp.hdrs import CONTENT_TYPE
import async_timeout

from homeassistant.const import CONTENT_TYPE_TEXT_PLAIN
from homeassistant.components.http import HomeAssistantView, KEY_AUTHENTICATED
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components.frontend import register_built_in_panel

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'hassio'
DEPENDENCIES = ['http']

TIMEOUT = 10

ADDON_REST_COMMANDS = {
    'install': ['POST'],
    'uninstall': ['POST'],
    'start': ['POST'],
    'stop': ['POST'],
    'update': ['POST'],
    'options': ['POST'],
    'info': ['GET'],
    'logs': ['GET'],
}


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the HASSio component."""
    try:
        host = os.environ['HASSIO']
    except KeyError:
        _LOGGER.error("No HassIO supervisor detect!")
        return False

    websession = async_get_clientsession(hass)
    hassio = HassIO(hass.loop, websession, host)

    api_ok = yield from hassio.is_connected()
    if not api_ok:
        _LOGGER.error("Not connected with HassIO!")
        return False

    hass.http.register_view(HassIOView(hassio))

    if 'frontend' in hass.config.components:
        register_built_in_panel(hass, 'hassio', 'Hass.io',
                                'mdi:access-point-network')

    return True


class HassIO(object):
    """Small API wrapper for HassIO."""

    def __init__(self, loop, websession, ip):
        """Initialze HassIO api."""
        self.loop = loop
        self.websession = websession
        self._ip = ip

    @asyncio.coroutine
    def is_connected(self):
        """Return True if it connected to HassIO supervisor.

        This method is a coroutine.
        """
        try:
            with async_timeout.timeout(TIMEOUT, loop=self.loop):
                request = yield from self.websession.get(
                    "http://{}{}".format(self._ip, "/supervisor/ping")
                )

                if request.status != 200:
                    _LOGGER.error("Ping return code %d.", request.status)
                    return False

                answer = yield from request.json()
                return answer and answer['result'] == 'ok'

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout on ping request")

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on ping request %s", err)

        return False

    @asyncio.coroutine
    def command_proxy(self, path, request):
        """Return a client request with proxy origin for HassIO supervisor.

        This method is a coroutine.
        """
        try:
            data = None
            headers = None
            with async_timeout.timeout(TIMEOUT, loop=self.loop):
                data = yield from request.read()
                if data:
                    headers = {CONTENT_TYPE: request.content_type}
                else:
                    data = None

            method = getattr(self.websession, request.method.lower())
            client = yield from method(
                "http://{}/{}".format(self._ip, path), data=data,
                headers=headers
            )

            return client

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on api %s request %s.", path, err)

        except asyncio.TimeoutError:
            _LOGGER.error("Client timeout error on api request %s.", path)

        raise HTTPBadGateway()


class HassIOView(HomeAssistantView):
    """HassIO view to handle base part."""

    name = "api:hassio"
    url = "/api/hassio/{path:.+}"
    requires_auth = False

    def __init__(self, hassio):
        """Initialize a hassio base view."""
        self.hassio = hassio

    @asyncio.coroutine
    def _handle(self, request, path):
        """Route data to hassio."""
        if path != 'panel' and not request[KEY_AUTHENTICATED]:
            return web.Response(status=401)

        client = yield from self.hassio.command_proxy(path, request)

        data = yield from client.read()
        if path.endswith('/logs'):
            return _create_response_log(client, data)
        return _create_response(client, data)

    get = _handle
    post = _handle


def _create_response(client, data):
    """Convert a response from client request."""
    return web.Response(
        body=data,
        status=client.status,
        content_type=client.content_type,
    )


def _create_response_log(client, data):
    """Convert a response from client request."""
    # Remove color codes
    log = re.sub(r"\x1b(\[.*?[@-~]|\].*?(\x07|\x1b\\))", "", data.decode())

    return web.Response(
        text=log,
        status=client.status,
        content_type=CONTENT_TYPE_TEXT_PLAIN,
    )
