"""
Exposes regular rest commands as services.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/hassio/
"""
import asyncio
import logging
import os

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.config import load_yaml_config_file
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

DOMAIN = 'hassio'

_LOGGER = logging.getLogger(__name__)

TIMEOUT = 900
DATA_HASSIO = 'hassio'

SERVICE_HOST_SHUTDOWN = 'host_shutdown'
SERVICE_HOST_REBOOT = 'host_reboot'
SERVICE_HOST_UPDATE = 'host_update'

SERVICE_NETWORK_OPTIONS = 'network_options'

SERVICE_SUPERVISOR_UPDATE = 'supervisor_update'
SERVICE_SUPERVISOR_OPTIONS = 'supervisor_options'

SERVICE_HOMEASSISTANT_UPDATE = 'homeassistant_update'

SERVICE_ADDON_INSTALL = 'addon_install'
SERVICE_ADDON_UNINSTALL = 'addon_uninstall'
SERVICE_ADDON_UPDATE = 'addon_update'
SERVICE_ADDON_START = 'addon_start'
SERVICE_ADDON_STOP = 'addon_stop'

ATTR_ADDON = 'addon'
ATTR_BETA = 'beta'
ATTR_OPTIONS = 'options'
ATTR_IP = 'ip'
ATTR_SSID = 'ssid'
ATTR_PASSWORD = 'password'
ATTR_VERSION = 'version'


SCHEMA_SERVICE_UPDATE = vol.Schema({
    vol.Optional(ATTR_VERSION): cv.string,
})

SCHEMA_SERVICE_SUPERVISOR_OPTIONS = vol.Schema({
    vol.Optional(ATTR_BETA): cv.boolean,
})

SCHEMA_SERVICE_NETWORK_OPTIONS = vol.Schema({
    vol.Optional(ATTR_IP): cv.string,
    vol.Optional(ATTR_SSID): cv.string,
    vol.Optional(ATTR_PASSWORD): cv.string,
})

SCHEMA_SERVICE_ADDONS = vol.Schema({
    vol.Required(ATTR_ADDON): cv.slug,
})

SCHEMA_SERVICE_ADDONS_START = SCHEMA_SERVICE_ADDONS.extend({
    vol.Optional(ATTR_OPTIONS): dict,
})

SCHEMA_SERVICE_ADDONS_VERSION = SCHEMA_SERVICE_ADDONS.extend({
    vol.Optional(ATTR_VERSION): cv.string,
})


@asyncio.coroutine
def async_setup(hass, config):
    """Setup the hassio component."""
    websession = async_get_clientsession(hass)
    hassio = HassIO(hass.loop, websession)

    if not hassio.connected:
        _LOGGER.error("No HassIO supervisor detect!")
        return False

    hass.data[DATA_HASSIO] = hassio

    descriptions = yield from hass.loop.run_in_executor(
        None, load_yaml_config_file, os.path.join(
            os.path.dirname(__file__), 'services.yaml'))

    @asyncio.coroutine
    def async_service_handler(service):
        """Handle HassIO service calls."""
        if service.service == SERVICE_HOST_UPDATE:
            yield from hassio.send_command(
                "/host/update", payload=service.data)
        elif service.service == SERVICE_HOST_REBOOT:
            yield from hassio.send_command("/host/reboot")
        elif service.service == SERVICE_HOST_SHUTDOWN:
            yield from hassio.send_command("/host/shutdown")
        elif service.service == SERVICE_NETWORK_OPTIONS:
            yield from hassio.send_command(
                "/network/options", payload=service.data)
        elif service.service == SERVICE_SUPERVISOR_UPDATE:
            yield from hassio.send_command(
                "/supervisor/update", payload=service.data)
        elif service.service == SERVICE_SUPERVISOR_OPTIONS:
            yield from hassio.send_command(
                "/supervisor/options", payload=service.data)
        elif service.service == SERVICE_HOMEASSISTANT_UPDATE:
            yield from hassio.send_command(
                "/homeassistant/update", payload=service.data)

    hass.services.async_register(
        DOMAIN, SERVICE_HOST_SHUTDOWN, async_service_handler,
        descriptions[DOMAIN][SERVICE_HOST_SHUTDOWN])
    hass.services.async_register(
        DOMAIN, SERVICE_HOST_REBOOT, async_service_handler,
        descriptions[DOMAIN][SERVICE_HOST_REBOOT])
    hass.services.async_register(
        DOMAIN, SERVICE_HOST_UPDATE, async_service_handler,
        descriptions[DOMAIN][SERVICE_HOST_UPDATE],
        schema=SCHEMA_SERVICE_UPDATE)
    hass.services.async_register(
        DOMAIN, SERVICE_SUPERVISOR_UPDATE, async_service_handler,
        descriptions[DOMAIN][SERVICE_SUPERVISOR_UPDATE],
        schema=SCHEMA_SERVICE_UPDATE)
    hass.services.async_register(
        DOMAIN, SERVICE_SUPERVISOR_OPTIONS, async_service_handler,
        descriptions[DOMAIN][SERVICE_SUPERVISOR_OPTIONS],
        schema=SCHEMA_SERVICE_SUPERVISOR_OPTIONS)
    hass.services.async_register(
        DOMAIN, SERVICE_NETWORK_OPTIONS, async_service_handler,
        descriptions[DOMAIN][SERVICE_NETWORK_OPTIONS],
        schema=SCHEMA_SERVICE_NETWORK_OPTIONS)
    hass.services.async_register(
        DOMAIN, SERVICE_HOMEASSISTANT_UPDATE, async_service_handler,
        descriptions[DOMAIN][SERVICE_HOMEASSISTANT_UPDATE],
        schema=SCHEMA_SERVICE_UPDATE)

    @asyncio.coroutine
    def async_service_handler_addons(service):
        """Handle HassIO service calls for addons."""
        addon = service.data[ATTR_ADDON]
        options = service.data.get(ATTR_OPTIONS)

        # extract version
        if ATTR_VERSION in service.data:
            version = {ATTR_VERSION: service.data[ATTR_VERSION]}
        else:
            version = None

        if service.service == SERVICE_ADDON_INSTALL:
            yield from hassio.send_command(
                "/addons/{}/install".format(addon), payload=version)
        elif service.service == SERVICE_ADDON_UNINSTALL:
            yield from hassio.send_command(
                "/addons/{}/uninstall".format(addon))
        elif service.service == SERVICE_ADDON_START:
            yield from hassio.send_command(
                "/addons/{}/start".format(addon), payload=options)
        elif service.service == SERVICE_ADDON_STOP:
            yield from hassio.send_command("/addons/{}/stop".format(addon))
        elif service.service == SERVICE_ADDON_UPDATE:
            yield from hassio.send_command(
                "/addons/{}/update".format(addon), payload=version)

    hass.services.async_register(
        DOMAIN, SERVICE_ADDON_UPDATE, async_service_handler_addons,
        descriptions[DOMAIN][SERVICE_ADDON_UPDATE],
        schema=SCHEMA_SERVICE_ADDONS_VERSION)
    hass.services.async_register(
        DOMAIN, SERVICE_ADDON_INSTALL, async_service_handler_addons,
        descriptions[DOMAIN][SERVICE_ADDON_INSTALL],
        schema=SCHEMA_SERVICE_ADDONS_VERSION)
    hass.services.async_register(
        DOMAIN, SERVICE_ADDON_UNINSTALL, async_service_handler_addons,
        descriptions[DOMAIN][SERVICE_ADDON_UNINSTALL],
        schema=SCHEMA_SERVICE_ADDONS)
    hass.services.async_register(
        DOMAIN, SERVICE_ADDON_START, async_service_handler_addons,
        descriptions[DOMAIN][SERVICE_ADDON_START],
        schema=SCHEMA_SERVICE_ADDONS_START)
    hass.services.async_register(
        DOMAIN, SERVICE_ADDON_STOP, async_service_handler_addons,
        descriptions[DOMAIN][SERVICE_ADDON_STOP],
        schema=SCHEMA_SERVICE_ADDONS)

    return True


class HassIO(object):
    """Small API wrapper for HassIO."""

    def __init__(self, loop, websession):
        """Initialze HassIO api."""
        self.loop = loop
        self.websession = websession
        try:
            self._ip = os.environ['HASSIO']
        except KeyError:
            self._ip = None

    @property
    def connected(self):
        """Return True if it connected to HassIO supervisor."""
        return self._ip is not None

    @asyncio.coroutine
    def send_command(self, cmd, payload=None):
        """Send request to API."""
        try:
            with async_timeout.timeout(TIMEOUT, loop=self.loop):
                request = yield from self.websession.get(
                    "http://{}{}".format(self._ip, cmd),
                    timeout=None, json=payload
                )

                if request.status != 200:
                    _LOGGER.error("%s return code %d.", cmd, request.status)
                    return

                answer = yield from request.json()
                if answer['result'] == 'ok':
                    return answer['data'] if answer['data'] else True

                _LOGGER.error("%s return error %s.", cmd, answer['message'])

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout on api request %s.", cmd)

        except aiohttp.ClientError:
            _LOGGER.error("Client error on api request %s.", cmd)

        return False
