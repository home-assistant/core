"""
Exposes regular rest commands as services.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/rest_command/
"""
import asyncio
import logging
import os

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.const import CONF_TIMEOUT
from homeassistant.config import load_yaml_config_file
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

DOMAIN = 'rest_command'

_LOGGER = logging.getLogger(__name__)

SERVICE_GET = 'get'
SERVICE_POST = 'post'
SERVICE_PUT = 'put'
SERVICE_DELETE = 'delete'

ATTR_URL = 'url'
ATTR_USERNAME = 'username'
ATTR_PASSWORD = 'password'
ATTR_PAYLOAD = 'payload'
ATTR_PARAMS = 'params'

DEFAULT_TIMEOUT = 10

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.Coerce(int),
    }),
}, extra=vol.ALLOW_EXTRA)

SERVICE_SCHEMA = vol.Schema({
    # pylint: disable=no-value-for-parameter
    vol.Required(ATTR_URL): vol.Url(),
    vol.Optional(ATTR_PARAMS): {cv.match_all: cv.string},
    vol.Optional(ATTR_USERNAME): cv.string,
    vol.Optional(ATTR_PASSWORD): cv.string,
})

SERVICE_PAYLOAD_SCHEMA = SERVICE_SCHEMA.extend({
    vol.Optional(ATTR_PAYLOAD): vol.Any({cv.match_all: cv.string}, cv.string),
})


@asyncio.coroutine
def async_setup(hass, config):
    """Setup the rest_command component."""
    conf = config.get(DOMAIN, {})

    descriptions = yield from hass.loop.run_in_executor(
        None, load_yaml_config_file, os.path.join(
            os.path.dirname(__file__), 'services.yaml')
    )

    @asyncio.coroutine
    def async_service_handler(call):
        """Execute a shell command service."""
        websession = async_get_clientsession(hass)

        params = None
        if ATTR_PARAMS in call.data:
            params = call.data[ATTR_PARAMS]

        auth = None
        if ATTR_USERNAME in call.data:
            username = call.data[ATTR_USERNAME]
            password = call.data.get(ATTR_PASSWORD, '')
            auth = aiohttp.BasicAuth(username, password=password)

        payload = None
        if ATTR_PAYLOAD in call.data:
            payload = call.data[ATTR_PAYLOAD]
            if isinstance(payload, str):
                payload = bytes(payload, 'utf-8')

        request = None
        try:
            with async_timeout.timeout(conf[CONF_TIMEOUT], loop=hass.loop):
                request = yield from getattr(websession, call.service)(
                    call.data[ATTR_URL],
                    params=params,
                    data=payload,
                    auth=auth
                )

                if request.status == 200:
                    _LOGGER.info("Success call %s.", request.url)
                    return

                _LOGGER.warning(
                    "Error %d on call %s.", request.status, request.url)
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout call %s.", request.url)

        except aiohttp.errors.ClientError:
            _LOGGER.error("Client error %s.", request.url)

        finally:
            if request is not None:
                yield from request.release()

    # register services

    for name in [SERVICE_GET, SERVICE_DELETE]:
        hass.services.async_register(
            DOMAIN, name, async_service_handler, descriptions[DOMAIN][name],
            schema=SERVICE_SCHEMA)

    for name in [SERVICE_POST, SERVICE_PUT]:
        hass.services.async_register(
            DOMAIN, name, async_service_handler, descriptions[DOMAIN][name],
            schema=SERVICE_PAYLOAD_SCHEMA)

    return True
