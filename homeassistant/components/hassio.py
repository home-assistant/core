"""
Exposes regular REST commands as services.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/hassio/
"""
import asyncio
from datetime import timedelta
import logging
import os
import re

import aiohttp
from aiohttp import web
from aiohttp.hdrs import CONTENT_TYPE
from aiohttp.web_exceptions import HTTPBadGateway
import async_timeout
import voluptuous as vol

from homeassistant.components import SERVICE_CHECK_CONFIG
from homeassistant.components.http import (
    CONF_API_PASSWORD, CONF_SERVER_HOST, CONF_SERVER_PORT,
    CONF_SSL_CERTIFICATE, KEY_AUTHENTICATED, HomeAssistantView)
from homeassistant.const import (
    CONF_TIME_ZONE, CONTENT_TYPE_TEXT_PLAIN, SERVER_PORT,
    SERVICE_HOMEASSISTANT_RESTART, SERVICE_HOMEASSISTANT_STOP)
from homeassistant.core import DOMAIN as HASS_DOMAIN
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import bind_hass
from homeassistant.util.dt import utcnow

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'hassio'
DEPENDENCIES = ['http']

X_HASSIO = 'X-HASSIO-KEY'

DATA_HOMEASSISTANT_VERSION = 'hassio_hass_version'
HASSIO_UPDATE_INTERVAL = timedelta(minutes=55)

SERVICE_ADDON_START = 'addon_start'
SERVICE_ADDON_STOP = 'addon_stop'
SERVICE_ADDON_RESTART = 'addon_restart'
SERVICE_ADDON_STDIN = 'addon_stdin'
SERVICE_HOST_SHUTDOWN = 'host_shutdown'
SERVICE_HOST_REBOOT = 'host_reboot'
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
    re.compile(r'^app-(es5|latest)/(index|hassio-app).html$'),
    re.compile(r'^addons/[^/]*/logo$')
}

SCHEMA_NO_DATA = vol.Schema({})

SCHEMA_ADDON = vol.Schema({
    vol.Required(ATTR_ADDON): cv.slug,
})

SCHEMA_ADDON_STDIN = SCHEMA_ADDON.extend({
    vol.Required(ATTR_INPUT): vol.Any(dict, cv.string)
})

SCHEMA_SNAPSHOT_FULL = vol.Schema({
    vol.Optional(ATTR_NAME): cv.string,
})

SCHEMA_SNAPSHOT_PARTIAL = SCHEMA_SNAPSHOT_FULL.extend({
    vol.Optional(ATTR_FOLDERS): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_ADDONS): vol.All(cv.ensure_list, [cv.string]),
})

SCHEMA_RESTORE_FULL = vol.Schema({
    vol.Required(ATTR_SNAPSHOT): cv.slug,
})

SCHEMA_RESTORE_PARTIAL = SCHEMA_RESTORE_FULL.extend({
    vol.Optional(ATTR_HOMEASSISTANT): cv.boolean,
    vol.Optional(ATTR_FOLDERS): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_ADDONS): vol.All(cv.ensure_list, [cv.string]),
})

MAP_SERVICE_API = {
    SERVICE_ADDON_START: ('/addons/{addon}/start', SCHEMA_ADDON, 60, False),
    SERVICE_ADDON_STOP: ('/addons/{addon}/stop', SCHEMA_ADDON, 60, False),
    SERVICE_ADDON_RESTART:
        ('/addons/{addon}/restart', SCHEMA_ADDON, 60, False),
    SERVICE_ADDON_STDIN:
        ('/addons/{addon}/stdin', SCHEMA_ADDON_STDIN, 60, False),
    SERVICE_HOST_SHUTDOWN: ('/host/shutdown', SCHEMA_NO_DATA, 60, False),
    SERVICE_HOST_REBOOT: ('/host/reboot', SCHEMA_NO_DATA, 60, False),
    SERVICE_SNAPSHOT_FULL:
        ('/snapshots/new/full', SCHEMA_SNAPSHOT_FULL, 300, True),
    SERVICE_SNAPSHOT_PARTIAL:
        ('/snapshots/new/partial', SCHEMA_SNAPSHOT_PARTIAL, 300, True),
    SERVICE_RESTORE_FULL:
        ('/snapshots/{snapshot}/restore/full', SCHEMA_RESTORE_FULL, 300, True),
    SERVICE_RESTORE_PARTIAL:
        ('/snapshots/{snapshot}/restore/partial', SCHEMA_RESTORE_PARTIAL, 300,
         True),
}


@callback
@bind_hass
def get_homeassistant_version(hass):
    """Return latest available Home Assistant version.

    Async friendly.
    """
    return hass.data.get(DATA_HOMEASSISTANT_VERSION)


@callback
@bind_hass
def is_hassio(hass):
    """Return true if hass.io is loaded.

    Async friendly.
    """
    return DOMAIN in hass.config.components


@bind_hass
@asyncio.coroutine
def async_check_config(hass):
    """Check configuration over Hass.io API."""
    result = yield from hass.data[DOMAIN].send_command(
        '/homeassistant/check', timeout=300)

    if not result:
        return "Hass.io config check API error"
    elif result['result'] == "error":
        return result['message']
    return None


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the Hass.io component."""
    try:
        host = os.environ['HASSIO']
    except KeyError:
        _LOGGER.error("No Hass.io supervisor detect")
        return False

    websession = hass.helpers.aiohttp_client.async_get_clientsession()
    hass.data[DOMAIN] = hassio = HassIO(hass.loop, websession, host)

    if not (yield from hassio.is_connected()):
        _LOGGER.error("Not connected with Hass.io")
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
        """Handle service calls for Hass.io."""
        api_command = MAP_SERVICE_API[service.service][0]
        data = service.data.copy()
        addon = data.pop(ATTR_ADDON, None)
        snapshot = data.pop(ATTR_SNAPSHOT, None)
        payload = None

        # Pass data to hass.io API
        if service.service == SERVICE_ADDON_STDIN:
            payload = data[ATTR_INPUT]
        elif MAP_SERVICE_API[service.service][3]:
            payload = data

        # Call API
        ret = yield from hassio.send_command(
            api_command.format(addon=addon, snapshot=snapshot),
            payload=payload, timeout=MAP_SERVICE_API[service.service][2]
        )

        if not ret or ret['result'] != "ok":
            _LOGGER.error("Error on Hass.io API: %s", ret['message'])

    for service, settings in MAP_SERVICE_API.items():
        hass.services.async_register(
            DOMAIN, service, async_service_handler, schema=settings[1])

    @asyncio.coroutine
    def update_homeassistant_version(now):
        """Update last available Home Assistant version."""
        data = yield from hassio.get_homeassistant_info()
        if data:
            hass.data[DATA_HOMEASSISTANT_VERSION] = \
                data['data']['last_version']

        hass.helpers.event.async_track_point_in_utc_time(
            update_homeassistant_version, utcnow() + HASSIO_UPDATE_INTERVAL)

    # Fetch last version
    yield from update_homeassistant_version(None)

    @asyncio.coroutine
    def async_handle_core_service(call):
        """Service handler for handling core services."""
        if call.service == SERVICE_HOMEASSISTANT_STOP:
            yield from hassio.send_command('/homeassistant/stop')
            return

        error = yield from async_check_config(hass)
        if error:
            _LOGGER.error(error)
            hass.components.persistent_notification.async_create(
                "Config error. See dev-info panel for details.",
                "Config validating", "{0}.check_config".format(HASS_DOMAIN))
            return

        if call.service == SERVICE_HOMEASSISTANT_RESTART:
            yield from hassio.send_command('/homeassistant/restart')

    # Mock core services
    for service in (SERVICE_HOMEASSISTANT_STOP, SERVICE_HOMEASSISTANT_RESTART,
                    SERVICE_CHECK_CONFIG):
        hass.services.async_register(
            HASS_DOMAIN, service, async_handle_core_service)

    return True


def _api_bool(funct):
    """Return a boolean."""
    @asyncio.coroutine
    def _wrapper(*argv, **kwargs):
        """Wrap function."""
        data = yield from funct(*argv, **kwargs)
        return data and data['result'] == "ok"

    return _wrapper


class HassIO(object):
    """Small API wrapper for Hass.io."""

    def __init__(self, loop, websession, ip):
        """Initialize Hass.io API."""
        self.loop = loop
        self.websession = websession
        self._ip = ip

    @_api_bool
    def is_connected(self):
        """Return true if it connected to Hass.io supervisor.

        This method return a coroutine.
        """
        return self.send_command("/supervisor/ping", method="get")

    def get_homeassistant_info(self):
        """Return data for Home Assistant.

        This method return a coroutine.
        """
        return self.send_command("/homeassistant/info", method="get")

    @_api_bool
    def update_hass_api(self, http_config):
        """Update Home Assistant API data on Hass.io.

        This method return a coroutine.
        """
        port = http_config.get(CONF_SERVER_PORT) or SERVER_PORT
        options = {
            'ssl': CONF_SSL_CERTIFICATE in http_config,
            'port': port,
            'password': http_config.get(CONF_API_PASSWORD),
            'watchdog': True,
        }

        if CONF_SERVER_HOST in http_config:
            options['watchdog'] = False
            _LOGGER.warning("Don't use 'server_host' options with Hass.io")

        return self.send_command("/homeassistant/options", payload=options)

    @_api_bool
    def update_hass_timezone(self, core_config):
        """Update Home-Assistant timezone data on Hass.io.

        This method return a coroutine.
        """
        return self.send_command("/supervisor/options", payload={
            'timezone': core_config.get(CONF_TIME_ZONE)
        })

    @asyncio.coroutine
    def send_command(self, command, method="post", payload=None, timeout=10):
        """Send API command to Hass.io.

        This method is a coroutine.
        """
        try:
            with async_timeout.timeout(timeout, loop=self.loop):
                request = yield from self.websession.request(
                    method, "http://{}{}".format(self._ip, command),
                    json=payload, headers={
                        X_HASSIO: os.environ.get('HASSIO_TOKEN', "")
                    })

                if request.status not in (200, 400):
                    _LOGGER.error(
                        "%s return code %d.", command, request.status)
                    return None

                answer = yield from request.json()
                return answer

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout on %s request", command)

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on %s request %s", command, err)

        return None

    @asyncio.coroutine
    def command_proxy(self, path, request):
        """Return a client request with proxy origin for Hass.io supervisor.

        This method is a coroutine.
        """
        read_timeout = _get_timeout(path)

        try:
            data = None
            headers = {X_HASSIO: os.environ.get('HASSIO_TOKEN', "")}
            with async_timeout.timeout(10, loop=self.loop):
                data = yield from request.read()
                if data:
                    headers[CONTENT_TYPE] = request.content_type
                else:
                    data = None

            method = getattr(self.websession, request.method.lower())
            client = yield from method(
                "http://{}/{}".format(self._ip, path), data=data,
                headers=headers, timeout=read_timeout
            )

            return client

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on api %s request %s", path, err)

        except asyncio.TimeoutError:
            _LOGGER.error("Client timeout error on API request %s", path)

        raise HTTPBadGateway()


class HassIOView(HomeAssistantView):
    """Hass.io view to handle base part."""

    name = "api:hassio"
    url = "/api/hassio/{path:.+}"
    requires_auth = False

    def __init__(self, hassio):
        """Initialize a Hass.io base view."""
        self.hassio = hassio

    @asyncio.coroutine
    def _handle(self, request, path):
        """Route data to Hass.io."""
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
    """Return timeout for a URL path."""
    for re_path in NO_TIMEOUT:
        if re_path.match(path):
            return 0
    return 300


def _need_auth(path):
    """Return if a path need authentication."""
    for re_path in NO_AUTH:
        if re_path.match(path):
            return False
    return True
