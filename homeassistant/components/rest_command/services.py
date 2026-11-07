"""Services for the REST command integration."""

from http import HTTPStatus
from json.decoder import JSONDecodeError
import logging
from typing import Any

import aiohttp
from aiohttp import hdrs
from multidict import CIMultiDict
import probatio
from yarl import URL

from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_HEADERS,
    CONF_METHOD,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_TIMEOUT,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_DIGEST_AUTHENTICATION,
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
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.util.ssl import SSLCipherList

from .const import (
    CONF_CONTENT_TYPE,
    CONF_INSECURE_CIPHER,
    CONF_SKIP_URL_ENCODING,
    DOMAIN,
)

_LOGGER = logging.getLogger(__package__)


@callback
def async_register_rest_command(
    hass: HomeAssistant, name: str, command_config: dict[str, Any]
) -> None:
    """Create service for rest command."""
    websession = async_get_clientsession(
        hass,
        command_config[CONF_VERIFY_SSL],
        ssl_cipher=(
            SSLCipherList.INSECURE
            if command_config[CONF_INSECURE_CIPHER]
            else SSLCipherList.PYTHON_DEFAULT
        ),
    )
    timeout = command_config[CONF_TIMEOUT]
    method = command_config[CONF_METHOD]

    template_url = command_config[CONF_URL]
    skip_url_encoding = command_config[CONF_SKIP_URL_ENCODING]

    basic_auth: tuple[str, str] | None = None
    digest_auth: tuple[str, str] | None = None
    if CONF_USERNAME in command_config:
        username = command_config[CONF_USERNAME]
        password = command_config.get(CONF_PASSWORD, "")
        if command_config.get(CONF_AUTHENTICATION) == HTTP_DIGEST_AUTHENTICATION:
            digest_auth = (username, password)
        else:
            basic_auth = (username, password)

    template_payload = None
    if CONF_PAYLOAD in command_config:
        template_payload = command_config[CONF_PAYLOAD]

    template_headers = command_config.get(CONF_HEADERS, {})

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

        _LOGGER.debug(
            "Calling %s %s with headers: %s and payload: %s",
            method,
            request_url,
            headers,
            payload,
        )

        # Kept out of the debug log above so the credentials are not logged.
        # Encoding here rather than at registration keeps a credential
        # outside latin-1 a failure of this call, not of the whole setup.
        request_headers = CIMultiDict(headers)
        if basic_auth is not None and hdrs.AUTHORIZATION not in request_headers:
            request_headers[hdrs.AUTHORIZATION] = aiohttp.encode_basic_auth(
                *basic_auth, encoding="latin1"
            )

        try:
            # Prepare request kwargs
            request_kwargs = {
                "data": payload,
                "headers": request_headers or None,
                "timeout": timeout,
            }

            # Add authentication
            if digest_auth is not None:
                request_kwargs["middlewares"] = (
                    aiohttp.DigestAuthMiddleware(*digest_auth),
                )

            async with getattr(websession, method)(
                URL(request_url, encoded=skip_url_encoding),
                **request_kwargs,
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
                    # always read the response to avoid closing
                    # the connection before the server has
                    # finished sending it, while avoiding
                    # excessive memory usage
                    async for _ in response.content.iter_chunked(1024):
                        pass

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
                return {
                    "content": _content,
                    "status": response.status,
                    "headers": {
                        key: values[0] if len(values) == 1 else values
                        for key in response.headers
                        if (values := response.headers.getall(key))
                    },
                }

        except TimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="timeout",
                translation_placeholders={"request_url": request_url},
            ) from err

        except aiohttp.ClientError as err:
            # pylint: disable-next=home-assistant-log-and-raise
            _LOGGER.error("Error fetching data: %s", err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="client_error",
                translation_placeholders={"request_url": request_url},
            ) from err

    # register services
    # Cannot be moved: action names come from the configuration
    # pylint: disable-next=home-assistant-action-registered-outside-services-module
    hass.services.async_register(
        DOMAIN,
        name,
        async_service_handler,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def _async_reload_service_handler(service: ServiceCall) -> None:
    """Remove all rest_commands and load new ones from config."""
    hass = service.hass
    conf = await async_integration_yaml_config(hass, DOMAIN)

    # conf will be None if the configuration can't be parsed
    if conf is None:
        return

    existing = hass.services.async_services_for_domain(DOMAIN)
    for existing_service in existing:
        if existing_service == SERVICE_RELOAD:
            continue
        hass.services.async_remove(DOMAIN, existing_service)

    for name, command_config in conf.get(DOMAIN, {}).items():
        async_register_rest_command(hass, name, command_config)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the REST command services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_RELOAD,
        _async_reload_service_handler,
        schema=probatio.Schema({}),
    )
