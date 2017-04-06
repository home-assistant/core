"""
Exposes regular rest commands as services.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/hassio/
"""
import asyncio
import logging
import os

import aiohttp
from aiohttp import web
from aiohttp.web_exceptions import HTTPBadGateway
import async_timeout
import voluptuous as vol

from homeassistant.config import load_yaml_config_file
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

DOMAIN = 'hassio'
DEPENDENCIES = ['http']

_LOGGER = logging.getLogger(__name__)

LONG_TASK_TIMEOUT = 900
DEFAULT_TIMEOUT = 10

SERVICE_HOST_SHUTDOWN = 'host_shutdown'
SERVICE_HOST_REBOOT = 'host_reboot'

SERVICE_HOST_UPDATE = 'host_update'
SERVICE_SUPERVISOR_UPDATE = 'supervisor_update'
SERVICE_HOMEASSISTANT_UPDATE = 'homeassistant_update'

SERVICE_ADDON_INSTALL = 'addon_install'
SERVICE_ADDON_UNINSTALL = 'addon_uninstall'
SERVICE_ADDON_UPDATE = 'addon_update'
SERVICE_ADDON_START = 'addon_start'
SERVICE_ADDON_STOP = 'addon_stop'

ATTR_ADDON = 'addon'
ATTR_VERSION = 'version'


SCHEMA_SERVICE_UPDATE = vol.Schema({
    vol.Optional(ATTR_VERSION): cv.string,
})

SCHEMA_SERVICE_ADDONS = vol.Schema({
    vol.Required(ATTR_ADDON): cv.slug,
})

SCHEMA_SERVICE_ADDONS_VERSION = SCHEMA_SERVICE_ADDONS.extend({
    vol.Optional(ATTR_VERSION): cv.string,
})


SERVICE_MAP = {
    SERVICE_HOST_SHUTDOWN: None,
    SERVICE_HOST_REBOOT: None,
    SERVICE_HOST_UPDATE: SCHEMA_SERVICE_UPDATE,
    SERVICE_SUPERVISOR_UPDATE: SCHEMA_SERVICE_UPDATE,
    SERVICE_HOMEASSISTANT_UPDATE: SCHEMA_SERVICE_UPDATE,
    SERVICE_ADDON_INSTALL: SCHEMA_SERVICE_ADDONS_VERSION,
    SERVICE_ADDON_UNINSTALL: SCHEMA_SERVICE_ADDONS,
    SERVICE_ADDON_START: SCHEMA_SERVICE_ADDONS,
    SERVICE_ADDON_STOP: SCHEMA_SERVICE_ADDONS,
    SERVICE_ADDON_UPDATE: SCHEMA_SERVICE_ADDONS_VERSION,
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

    # register base api views
    for base in ('host', 'homeassistant'):
        hass.http.register_view(HassIOBaseView(hassio, base))
    for base in ('supervisor', 'network'):
        hass.http.register_view(HassIOBaseEditView(hassio, base))

    # register view for addons
    hass.http.register_view(HassIOAddonsView(hassio))

    @asyncio.coroutine
    def async_service_handler(service):
        """Handle HassIO service calls."""
        addon = service.data.get(ATTR_ADDON)
        if ATTR_VERSION in service.data:
            version = {ATTR_VERSION: service.data[ATTR_VERSION]}
        else:
            version = None

        # map to api call
        if service.service == SERVICE_HOST_UPDATE:
            yield from hassio.send_command(
                "/host/update", payload=version)
        elif service.service == SERVICE_HOST_REBOOT:
            yield from hassio.send_command("/host/reboot")
        elif service.service == SERVICE_HOST_SHUTDOWN:
            yield from hassio.send_command("/host/shutdown")
        elif service.service == SERVICE_SUPERVISOR_UPDATE:
            yield from hassio.send_command(
                "/supervisor/update", payload=version)
        elif service.service == SERVICE_HOMEASSISTANT_UPDATE:
            yield from hassio.send_command(
                "/homeassistant/update", payload=version,
                timeout=LONG_TASK_TIMEOUT)
        elif service.service == SERVICE_ADDON_INSTALL:
            yield from hassio.send_command(
                "/addons/{}/install".format(addon), payload=version,
                timeout=LONG_TASK_TIMEOUT)
        elif service.service == SERVICE_ADDON_UNINSTALL:
            yield from hassio.send_command(
                "/addons/{}/uninstall".format(addon))
        elif service.service == SERVICE_ADDON_START:
            yield from hassio.send_command("/addons/{}/start".format(addon))
        elif service.service == SERVICE_ADDON_STOP:
            yield from hassio.send_command("/addons/{}/stop".format(addon))
        elif service.service == SERVICE_ADDON_UPDATE:
            yield from hassio.send_command(
                "/addons/{}/update".format(addon), payload=version,
                timeout=LONG_TASK_TIMEOUT)

    descriptions = yield from hass.loop.run_in_executor(
        None, load_yaml_config_file, os.path.join(
            os.path.dirname(__file__), 'services.yaml'))

    for service, schema in SERVICE_MAP.items():
        hass.services.async_register(
            DOMAIN, service, async_service_handler,
            descriptions[DOMAIN][service], schema=schema)

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

        Return a coroutine.
        """
        return self.send_command("/supervisor/ping")

    @asyncio.coroutine
    def send_command(self, cmd, payload=None, timeout=DEFAULT_TIMEOUT):
        """Send request to API."""
        answer = yield from self.send_raw(cmd, payload=payload)
        if answer['result'] == 'ok':
            return answer['data'] if answer['data'] else True

        _LOGGER.error("%s return error %s.", cmd, answer['message'])
        return False

    @asyncio.coroutine
    def send_raw(self, cmd, payload=None, timeout=DEFAULT_TIMEOUT):
        """Send raw request to API."""
        try:
            with async_timeout.timeout(timeout, loop=self.loop):
                request = yield from self.websession.get(
                    "http://{}{}".format(self._ip, cmd),
                    timeout=None, json=payload
                )

                if request.status != 200:
                    _LOGGER.error("%s return code %d.", cmd, request.status)
                    return

                return (yield from request.json())

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout on api request %s.", cmd)

        except aiohttp.ClientError:
            _LOGGER.error("Client error on api request %s.", cmd)


class HassIOBaseView(HomeAssistantView):
    """HassIO view to handle base part."""

    requires_auth = True

    def __init__(self, hassio, base):
        """Initialize a hassio base view."""
        self.hassio = hassio
        self._url_info = "/{}/info".format(base)

        self.url = "/api/hassio/{}".format(base)
        self.name = "api:hassio:{}".format(base)

    @asyncio.coroutine
    def get(self, request):
        """Get base data."""
        data = yield from self.hassio.send_command(self._url_info)
        if not data:
            raise HTTPBadGateway()
        return web.json_response(data)


class HassIOBaseEditView(HassIOBaseView):
    """HassIO view to handle base with options support."""

    def __init__(self, hassio, base):
        """Initialize a hassio base edit view."""
        super().__init__(hassio, base)
        self._url_options = "/{}/options".format(base)

    @asyncio.coroutine
    def post(self, request):
        """Set options on host."""
        data = yield from request.json()

        response = yield from self.hassio.send_raw(
            self._url_options, payload=data)
        if not response:
            raise HTTPBadGateway()
        return web.json_response(response)


class HassIOAddonsView(HomeAssistantView):
    """HassIO view to handle addons part."""

    requires_auth = True
    url = "/api/hassio/addons/{addon}"
    name = "api:hassio:addons"

    def __init__(self, hassio):
        """Initialize a hassio addon view."""
        self.hassio = hassio

    @asyncio.coroutine
    def get(self, request, addon):
        """Get addon data."""
        data = yield from self.hassio.send_command(
            "/addons/{}/info".format(addon))
        if not data:
            raise HTTPBadGateway()
        return web.json_response(data)

    @asyncio.coroutine
    def post(self, request, addon):
        """Set options on host."""
        data = yield from request.json()

        response = yield from self.hassio.send_raw(
            "/addons/{}/options".format(addon), payload=data)
        if not response:
            raise HTTPBadGateway()
        return web.json_response(response)
