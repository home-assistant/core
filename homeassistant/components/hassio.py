"""
Exposes regular rest commands as services.

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

from homeassistant.const import CONTENT_TYPE_TEXT_PLAIN, CONTENT_TYPE_JSON
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.aiohttp_client import async_get_clientsession

DOMAIN = 'hassio'
DEPENDENCIES = ['http']

_LOGGER = logging.getLogger(__name__)

TIMEOUT = 10

HASSIO_REST_COMMANDS = {
    "host": ["shutdown", "restart", "update", "info"],
    "supervisor": ["info", "update", "options", "reload", "logs"],
    "homeassistant": ["info", "update", "logs"],
    "network": ["info", "options"],
    "addons": [
        "install", "uninstall", "start", "stop", "update", "options", "info",
        "logs"
    ]
}


@asyncio.coroutine
def async_setup(hass, config):
    """Setup the hassio component."""
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

    # register view
    for base, commands in HASSIO_REST_COMMANDS.items():
        for command in commands:
            if base == "addons":
                hass.http.register_view(HassIOAddonsView(hassio, command))
            else:
                hass.http.register_view(HassIOView(hassio, base, command))

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
                if answer and answer['result'] == 'ok':
                    return True

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout on ping request")

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on ping request %s", err)

        return False

    @asyncio.coroutine
    def command_proxy(self, cmd, request):
        """Return a client request with proxy origin for HassIO supervisor.

        This method is a coroutine.
        """
        try:
            data = None
            headers = None
            with async_timeout.timeout(TIMEOUT, loop=self.loop):
                if request.content_type in \
                        (CONTENT_TYPE_JSON, CONTENT_TYPE_TEXT_PLAIN):
                    data = yield from request.read()
                    headers = {CONTENT_TYPE: request.content_type}

            client = yield from self.websession.get(
                "http://{}{}".format(self._ip, cmd), data=data, headers=headers
            )

            return client

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on api %s request %s.", cmd, err)

        except asyncio.TimeoutError:
            _LOGGER.error("Client timeout error on api request %s.", cmd)

        raise HTTPBadGateway()


class HassIOBaseView(HomeAssistantView):
    """HassIO view to handle proxy part part."""

    @staticmethod
    def _create_response(client, data):
        """Convert a response from client request."""
        return web.Response(
            body=data,
            status=client.status,
            content_type=client.content_type,
        )

    @staticmethod
    def _create_response_log(client, data):
        """Convert a response from client request."""
        log = re.sub(r"\x1b(\[.*?[@-~]|\].*?(\x07|\x1b\\))", "", data.decode())

        return web.Response(
            text=log,
            status=client.status,
            content_type=CONTENT_TYPE_TEXT_PLAIN,
        )


class HassIOView(HassIOBaseView):
    """HassIO view to handle base part."""

    requires_auth = True

    def __init__(self, hassio, base, command):
        """Initialize a hassio base view."""
        self.hassio = hassio
        self._cmd = "/{}/{}".format(base, command)
        self._command = command

        self.url = "/api/hassio/{}/{}".format(base, command)
        self.name = "api:hassio:{}:{}".format(base, command)

    @asyncio.coroutine
    def get(self, request):
        """Route data to hassio."""
        client = yield from self.hassio.command_proxy(self._cmd, request)

        data = yield from client.read()
        if self._command == "logs":
            return self._create_response_log(client, data)
        return self._create_response(client, data)


class HassIOAddonsView(HassIOBaseView):
    """HassIO view to handle addon part."""

    requires_auth = True

    def __init__(self, hassio, command):
        """Initialize a hassio base view."""
        self.hassio = hassio
        self._command = command

        self.url = "/api/hassio/addons/{}/{}".format("{addon}", command)
        self.name = "api:hassio:addons:{}".format(command)

    @asyncio.coroutine
    def get(self, request, addon):
        """Route addon data to hassio."""
        addon_cmd = "/addons/{}/{}".format(addon, self._command)
        client = yield from self.hassio.command_proxy(addon_cmd, request)

        data = yield from client.read()
        if self._command == "logs":
            return self._create_response_log(client, data)
        return self._create_response(client, data)
