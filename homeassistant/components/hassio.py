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
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONTENT_TYPE_TEXT_PLAIN, SERVER_PORT, CONF_TIME_ZONE)
from homeassistant.components.http import (
    HomeAssistantView, KEY_AUTHENTICATED, CONF_API_PASSWORD, CONF_SERVER_PORT,
    CONF_SSL_CERTIFICATE)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'hassio'
DEPENDENCIES = ['http']

SERVICE_ADDON_START = 'addon_start'
SERVICE_ADDON_STOP = 'addon_stop'
SERVICE_ADDON_RESTART = 'addon_restart'
SERVICE_ADDON_STDIN = 'addon_stdin'
SERVICE_ADDON_UPDATE = 'addon_update'
SERVICE_HOST_SHUTDOWN = 'host_shutdown'
SERVICE_HOST_REBOOT = 'host_reboot'
SERVICE_HOST_UPDATE = 'host_update'
SERVICE_SNAPSHOT_FULL = 'snapshot_full'
SERVICE_SNAPSHOT_PARTIAL = 'snapshot_partial'
SERVICE_RESTORE_FULL = 'restore_full'
SERVICE_RESTORE_PARTIAL = 'restore_partial'

ATTR_ADDON = 'addon'
ATTR_INPUT = 'input'
ATTR_SNAPSHOT = 'snapshot'
ATTR_ADDONS = 'addons'
ATTR_FOLDERS = 'folders'
ATTR_HOMEASSISTANT = 'homeassistant'
ATTR_NAME = 'name'

NO_TIMEOUT = {
    re.compile(r'^homeassistant/update$'),
    re.compile(r'^host/update$'),
    re.compile(r'^supervisor/update$'),
    re.compile(r'^addons/[^/]*/update$'),
    re.compile(r'^addons/[^/]*/install$'),
    re.compile(r'^addons/[^/]*/rebuild$'),
    re.compile(r'^snapshots/.*/full$'),
    re.compile(r'^snapshots/.*/partial$'),
}

NO_AUTH = {
    re.compile(r'^panel_(es5|latest)$'), re.compile(r'^addons/[^/]*/logo$')
}

SCHEMA_ADDON = vol.Schema({
    vol.Required(ATTR_ADDON): cv.slug,
})

SCHEMA_ADDON_STDIN = SCHEMA_ADDON.extend({
    vol.Required(ATTR_INPUT): vol.Any(dict, cv.string)
})

SCHEMA_SNAPSHOT_FULL = vol.Schema({
    vol.Optional(ATTR_NAME): cv.string,
})

SCHEMA_SNAPSHOT_FULL = SCHEMA_SNAPSHOT_FULL.extend({
    vol.Optional(ATTR_FOLDERS): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_ADDONS): vol.All(cv.ensure_list, [cv.string]),
})

SCHEMA_RESTORE_FULL = vol.Schema({
    vol.Required(ATTR_SNAPSHOT): cv.slug,
})

SCHEMA_RESTORE_PARTIAL = vol.Schema({
    vol.Optional(ATTR_HOMEASSISTANT): cv.boolean,
    vol.Optional(ATTR_FOLDERS): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_ADDONS): vol.All(cv.ensure_list, [cv.string]),
})

MAP_SERVICE_API = {
    SERVICE_ADDON_START: ('/addons/{addon}/start', SCHEMA_ADDON, 60),
    SERVICE_ADDON_STOP: ('/addons/{addon}/stop', SCHEMA_ADDON, 60),
    SERVICE_ADDON_RESTART: ('/addons/{addon}/restart', SCHEMA_ADDON, 60),
    SERVICE_ADDON_UPDATE: ('/addons/{addon}/update', SCHEMA_ADDON, 300),
    SERVICE_ADDON_STDIN: ('/addons/{addon}/stdin', SCHEMA_ADDON_STDIN, 60),
    SERVICE_HOST_SHUTDOWN: ('/host/shutdown', None, 60),
    SERVICE_HOST_REBOOT: ('/host/reboot', None, 60),
    SERVICE_HOST_UPDATE: ('/host/update', None, 300),
    SERVICE_SNAPSHOT_FULL: ('/snapshots/new/full', SERVICE_SNAPSHOT_FULL, 300),
    SERVICE_SNAPSHOT_PARTIAL: ('/snapshots/new/partial',
                               SERVICE_SNAPSHOT_PARTIAL, 300),
    SERVICE_RESTORE_FULL: ('/snapshots/{snapshot}/restore/full',
                           SERVICE_RESTORE_FULL, 300),
    SERVICE_RESTORE_PARTIAL: ('/snapshots/{snapshot}/restore/partial',
                              SERVICE_RESTORE_PARTIAL, 300),
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

    if not (yield from hassio.is_connected()):
        _LOGGER.error("Not connected with HassIO!")
        return False

    hass.http.register_view(HassIOView(hassio))

    if 'frontend' in hass.config.components:
        yield from hass.components.frontend.async_register_built_in_panel(
            'hassio', 'Hass.io', 'mdi:access-point-network')

    if 'http' in config:
        yield from hassio.update_hass_api(config['http'])

    if 'homeassistant' in config:
        yield from hassio.update_hass_timezone(config['homeassistant'])

    @asyncio.coroutine
    def async_service_handler(service):
        """Handle service calls for HassIO."""
        api_command = MAP_SERVICE_API[service.service][0]
        addon = service.data.pop(ATTR_ADDON)
        snapshot = service.data.pop(ATTR_SNAPSHOT)
        payload = None

        # Pass data to hass.io API
        if ATTR_INPUT in service.data:
            payload = service.data[ATTR_INPUT]
        elif service.data:
            payload = service.data.copy()

        # Call API
        yield from hassio.send_command(
            api_command.format(addon=addon, snapshot=snapshot),
            payload=payload, timeout=MAP_SERVICE_API[service.service][2]
        )

    for service, settings in MAP_SERVICE_API.items():
        hass.services.async_register(
            DOMAIN, service, async_service_handler, schema=settings[1])

    return True


class HassIO(object):
    """Small API wrapper for HassIO."""

    def __init__(self, loop, websession, ip):
        """Initialze HassIO api."""
        self.loop = loop
        self.websession = websession
        self._ip = ip

    def is_connected(self):
        """Return True if it connected to HassIO supervisor.

        This method return a coroutine.
        """
        return self.send_command("/supervisor/ping", method="get")

    def update_hass_api(self, http_config):
        """Update Home-Assistant API data on HassIO.

        This method return a coroutine.
        """
        port = http_config.get(CONF_SERVER_PORT) or SERVER_PORT
        options = {
            'ssl': CONF_SSL_CERTIFICATE in http_config,
            'port': port,
            'password': http_config.get(CONF_API_PASSWORD),
        }

        return self.send_command("/homeassistant/options", payload=options)

    def update_hass_timezone(self, core_config):
        """Update Home-Assistant timezone data on HassIO.

        This method return a coroutine.
        """
        return self.send_command("/supervisor/options", payload={
            'timezone': core_config.get(CONF_TIME_ZONE)
        })

    @asyncio.coroutine
    def send_command(self, command, method="post", payload=None, timeout=10):
        """Send API command to HassIO.

        This method is a coroutine.
        """
        try:
            with async_timeout.timeout(timeout, loop=self.loop):
                request = yield from self.websession.request(
                    method, "http://{}{}".format(self._ip, command),
                    json=payload)

                if request.status != 200:
                    _LOGGER.error(
                        "%s return code %d.", command, request.status)
                    return False

                answer = yield from request.json()
                return answer and answer['result'] == 'ok'

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout on %s request", command)

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on %s request %s", command, err)

        return False

    @asyncio.coroutine
    def command_proxy(self, path, request):
        """Return a client request with proxy origin for HassIO supervisor.

        This method is a coroutine.
        """
        read_timeout = _get_timeout(path)

        try:
            data = None
            headers = None
            with async_timeout.timeout(10, loop=self.loop):
                data = yield from request.read()
                if data:
                    headers = {CONTENT_TYPE: request.content_type}
                else:
                    data = None

            method = getattr(self.websession, request.method.lower())
            client = yield from method(
                "http://{}/{}".format(self._ip, path), data=data,
                headers=headers, timeout=read_timeout
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
        if _need_auth(path) and not request[KEY_AUTHENTICATED]:
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


def _get_timeout(path):
    """Return timeout for a url path."""
    for re_path in NO_TIMEOUT:
        if re_path.match(path):
            return 0
    return 300


def _need_auth(path):
    """Return if a path need a auth."""
    for re_path in NO_AUTH:
        if re_path.match(path):
            return False
    return True
