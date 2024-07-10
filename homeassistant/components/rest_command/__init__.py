"""Support for exposing regular REST commands as services."""

from __future__ import annotations

from http import HTTPStatus
from json.decoder import JSONDecodeError
import logging
from typing import Any

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
    SERVICE_RELOAD,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.reload import async_integration_yaml_config
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

    async def reload_service_handler(service: ServiceCall) -> None:
        """Remove all rest_commands and load new ones from config."""
        conf = await async_integration_yaml_config(hass, DOMAIN)

        # conf will be None if the configuration can't be parsed
        if conf is None:
            return

        existing = hass.services.async_services_for_domain(DOMAIN)
        for existing_service in existing:
            if existing_service == SERVICE_RELOAD:
                continue
            hass.services.async_remove(DOMAIN, existing_service)

        for name, command_config in conf[DOMAIN].items():
            async_register_rest_command(name, command_config)

    @callback
    def async_register_rest_command(name: str, command_config: dict[str, Any]) -> None:
        """Create service for rest command."""
        websession = async_get_clientsession(hass, command_config[CONF_VERIFY_SSL])
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

        template_headers = command_config.get(CONF_HEADERS, {})
        for template_header in template_headers.values():
            template_header.hass = hass

        content_type = command_config.get(CONF_CONTENT_TYPE)

        async def async_service_handler(service: ServiceCall) -> ServiceResponse:
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

            headers = {}
            for header_name, template_header in template_headers.items():
                headers[header_name] = template_header.async_render(
                    variables=service.data, parse_result=False
                )

            if content_type:
                headers[hdrs.CONTENT_TYPE] = content_type

            try:
                async with getattr(websession, method)(
                    request_url,
                    data=payload,
                    auth=auth,
                    headers=headers or None,
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

                    if not service.return_response:
                        return None

                    _content = None
                    try:
                        if response.content_type == "application/json":
                            _content = await response.json()
                        else:
                            _content = await response.text()
                    except (JSONDecodeError, AttributeError) as err:
                        raise HomeAssistantError(
                            translation_domain=DOMAIN,
                            translation_key="decoding_error",
                            translation_placeholders={
                                "request_url": request_url,
                                "decoding_type": "JSON",
                            },
                        ) from err

                    except UnicodeDecodeError as err:
                        raise HomeAssistantError(
                            translation_domain=DOMAIN,
                            translation_key="decoding_error",
                            translation_placeholders={
                                "request_url": request_url,
                                "decoding_type": "text",
                            },
                        ) from err
                    return {"content": _content, "status": response.status}

            except TimeoutError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="timeout",
                    translation_placeholders={"request_url": request_url},
                ) from err

            except aiohttp.ClientError as err:
                _LOGGER.error("Error fetching data: %s", err)
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="client_error",
                    translation_placeholders={"request_url": request_url},
                ) from err

        # register services
        hass.services.async_register(
            DOMAIN,
            name,
            async_service_handler,
            supports_response=SupportsResponse.OPTIONAL,
        )

    for name, command_config in config[DOMAIN].items():
        async_register_rest_command(name, command_config)

    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, reload_service_handler, schema=vol.Schema({})
    )

    return True
