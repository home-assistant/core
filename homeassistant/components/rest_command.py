"""
Exposes regular rest commands as services.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/rest_command/
"""
import asyncio
import logging

import aiohttp
from aiohttp import hdrs
import async_timeout
import voluptuous as vol
import requests
from requests.auth import HTTPDigestAuth

from homeassistant.const import (
    CONF_TIMEOUT, CONF_USERNAME, CONF_PASSWORD, CONF_URL, CONF_PAYLOAD,
    CONF_METHOD, CONF_AUTHENTICATION,
    HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

DOMAIN = 'rest_command'

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10
DEFAULT_METHOD = 'get'

SUPPORT_REST_METHODS = [
    'get',
    'post',
    'put',
    'delete',
]

CONF_CONTENT_TYPE = 'content_type'

COMMAND_SCHEMA = vol.Schema({
    vol.Required(CONF_URL): cv.template,
    vol.Optional(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION):
        vol.In([HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]),
    vol.Optional(CONF_METHOD, default=DEFAULT_METHOD):
        vol.All(vol.Lower, vol.In(SUPPORT_REST_METHODS)),
    vol.Inclusive(CONF_USERNAME, 'authentication'): cv.string,
    vol.Inclusive(CONF_PASSWORD, 'authentication'): cv.string,
    vol.Optional(CONF_PAYLOAD): cv.template,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.Coerce(int),
    vol.Optional(CONF_CONTENT_TYPE): cv.string
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: COMMAND_SCHEMA,
    }),
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the REST command component."""
    websession = async_get_clientsession(hass)

    def async_register_rest_command(name, command_config):
        """Create service for rest command."""
        timeout = command_config[CONF_TIMEOUT]
        method = command_config[CONF_METHOD]

        template_url = command_config[CONF_URL]
        template_url.hass = hass

        auth = None
        if CONF_USERNAME in command_config:
            username = command_config[CONF_USERNAME]
            password = command_config.get(CONF_PASSWORD, '')
            
            if command_config[CONF_AUTHENTICATION] == HTTP_DIGEST_AUTHENTICATION:
                auth = HTTPDigestAuth(username, password)
            else:
                auth = aiohttp.BasicAuth(username, password=password)

        template_payload = None
        if CONF_PAYLOAD in command_config:
            template_payload = command_config[CONF_PAYLOAD]
            template_payload.hass = hass

        headers = None
        if CONF_CONTENT_TYPE in command_config:
            content_type = command_config[CONF_CONTENT_TYPE]
            headers = {hdrs.CONTENT_TYPE: content_type}

        @asyncio.coroutine
        def async_service_handler(service):
            """Execute a shell command service."""
            payload = None
            if template_payload:
                payload = bytes(
                    template_payload.async_render(variables=service.data),
                    'utf-8')

            try:
                # aiohttp don't support DigestAuth yet
                if command_config[CONF_AUTHENTICATION] == HTTP_DIGEST_AUTHENTICATION:
                    def fetch():
                        """Make request"""
                        try:
                            url = template_url.async_render(variables=service.data)
                            if command_config[CONF_METHOD] == 'get':
                                request = requests.get(url, data=payload, timeout=10, auth=auth, headers=headers)
                            elif command_config[CONF_METHOD] == 'post':
                                request = requests.post(url, data=payload, timeout=10, auth=auth, headers=headers)
                            elif command_config[CONF_METHOD] == 'delete':
                                request = requests.delete(url, data=payload, timeout=10, auth=auth, headers=headers)
                            elif command_config[CONF_METHOD] == 'put':
                                request = requests.put(url, data=payload, timeout=10, auth=auth, headers=headers)
                            elif command_config[CONF_METHOD] == 'head':
                                request = requests.head(url, data=payload, timeout=10, auth=auth, headers=headers)
                            elif command_config[CONF_METHOD] == 'options':
                                request = requests.options(url, data=payload, timeout=10, auth=auth, headers=headers)
                                
                            return request
                        except requests.exceptions.RequestException as error:
                            _LOGGER.error("Rest command error %s.", url)

                        response = yield from self.hass.async_add_job(
                            fetch)
                else:    
                    with async_timeout.timeout(timeout, loop=hass.loop):
                        request = yield from getattr(websession, method)(
                            template_url.async_render(variables=service.data),
                            data=payload,
                            auth=auth,
                            headers=headers
                        )

                if request.status < 400:
                    _LOGGER.info("Success call %s.", request.url)
                else:
                    _LOGGER.warning(
                        "Error %d on call %s.", request.status, request.url)

            except asyncio.TimeoutError:
                _LOGGER.warning("Timeout call %s.", request.url)

            except aiohttp.ClientError:
                _LOGGER.error("Client error %s.", request.url)

        # register services
        hass.services.async_register(DOMAIN, name, async_service_handler)

    for command, command_config in config[DOMAIN].items():
        async_register_rest_command(command, command_config)

    return True
