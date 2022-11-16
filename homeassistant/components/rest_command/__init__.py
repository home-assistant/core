"""Support for exposing regular REST commands as services."""
import asyncio
from http import HTTPStatus
import logging

import aiohttp
from aiohttp import hdrs
import voluptuous as vol

from homeassistant.const import (
    CONF_HEADERS,
    CONF_METHOD,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_TIMEOUT,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

DOMAIN = "rest_command"

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10
DEFAULT_METHOD = "get"
DEFAULT_VERIFY_SSL = True

SUPPORT_REST_METHODS = ["get", "patch", "post", "put", "delete"]

CONF_CONTENT_TYPE = "content_type"

COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): cv.template,
        vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): vol.All(
            vol.Lower, vol.In(SUPPORT_REST_METHODS)
        ),
        vol.Optional(CONF_HEADERS): vol.Schema({cv.string: cv.template}),
        vol.Inclusive(CONF_USERNAME, "authentication"): cv.string,
        vol.Inclusive(CONF_PASSWORD, "authentication"): cv.string,
        vol.Optional(CONF_PAYLOAD): cv.template,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.Coerce(int),
        vol.Optional(CONF_CONTENT_TYPE): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: cv.schema_with_slug_keys(COMMAND_SCHEMA)}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the REST command component."""

    @callback
    def async_register_rest_command(name, command_config):
        """Create service for rest command."""
        websession = async_get_clientsession(hass, command_config.get(CONF_VERIFY_SSL))
        timeout = command_config[CONF_TIMEOUT]
        method = command_config[CONF_METHOD]

        template_url = command_config[CONF_URL]
        template_url.hass = hass

        auth = None
        if CONF_USERNAME in command_config:
            username = command_config[CONF_USERNAME]
            password = command_config.get(CONF_PASSWORD, "")
            auth = aiohttp.BasicAuth(username, password=password)

        template_payload = None
        if CONF_PAYLOAD in command_config:
            template_payload = command_config[CONF_PAYLOAD]
            template_payload.hass = hass

        template_headers = None
        if CONF_HEADERS in command_config:
            template_headers = command_config[CONF_HEADERS]
            for template_header in template_headers.values():
                template_header.hass = hass

        content_type = None
        if CONF_CONTENT_TYPE in command_config:
            content_type = command_config[CONF_CONTENT_TYPE]

        async def async_service_handler(service: ServiceCall) -> None:
            """Execute a shell command service."""
            payload = None
            if template_payload:
                payload = bytes(
                    template_payload.async_render(
                        variables=service.data, parse_result=False
                    ),
                    "utf-8",
                )

            request_url = template_url.async_render(
                variables=service.data, parse_result=False
            )

            headers = None
            if template_headers:
                headers = {}
                for header_name, template_header in template_headers.items():
                    headers[header_name] = template_header.async_render(
                        variables=service.data, parse_result=False
                    )

            if content_type:
                if headers is None:
                    headers = {}
                headers[hdrs.CONTENT_TYPE] = content_type

            try:
                async with getattr(websession, method)(
                    request_url,
                    data=payload,
                    auth=auth,
                    headers=headers,
                    timeout=timeout,
                ) as response:

                    if response.status < HTTPStatus.BAD_REQUEST:
                        _LOGGER.debug(
                            "Success. Url: %s. Status code: %d. Payload: %s",
                            response.url,
                            response.status,
                            payload,
                        )
                    else:
                        _LOGGER.warning(
                            "Error. Url: %s. Status code %d. Payload: %s",
                            response.url,
                            response.status,
                            payload,
                        )

            except asyncio.TimeoutError:
                _LOGGER.warning("Timeout call %s", request_url)

            except aiohttp.ClientError as err:
                _LOGGER.error(
                    "Client error. Url: %s. Error: %s",
                    request_url,
                    err,
                )

        # register services
        hass.services.async_register(DOMAIN, name, async_service_handler)

    for name, command_config in config[DOMAIN].items():
        async_register_rest_command(name, command_config)

    return True
