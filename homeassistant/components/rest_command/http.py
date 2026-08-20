"""HTTP request handling for RESTful Command."""

from http import HTTPStatus
from json.decoder import JSONDecodeError
import logging
from typing import Any

import aiohttp
from aiohttp import hdrs
from yarl import URL

from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_METHOD,
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_TOKEN,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant, ServiceResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.ssl import SSLCipherList

from .const import (
    AUTHENTICATION_BEARER,
    CONF_CONTENT_TYPE,
    CONF_INSECURE_CIPHER,
    CONF_SKIP_URL_ENCODING,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class RestCommandRequest:
    """Execute a configured RESTful Command request."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize the request."""
        self._config = config
        self._websession = async_get_clientsession(
            hass,
            config[CONF_VERIFY_SSL],
            ssl_cipher=(
                SSLCipherList.INSECURE
                if config[CONF_INSECURE_CIPHER]
                else SSLCipherList.PYTHON_DEFAULT
            ),
        )

    async def async_call(
        self,
        request_url: str,
        payload: str | None,
        headers: dict[str, str],
        return_response: bool,
    ) -> ServiceResponse:
        """Send the configured request."""
        method = self._config[CONF_METHOD]
        if content_type := self._config.get(CONF_CONTENT_TYPE):
            headers[hdrs.CONTENT_TYPE] = content_type
        if self._config.get(CONF_AUTHENTICATION) == AUTHENTICATION_BEARER:
            headers[hdrs.AUTHORIZATION] = f"Bearer {self._config[CONF_TOKEN]}"

        request_kwargs: dict[str, Any] = {
            "data": payload.encode() if payload is not None else None,
            "headers": headers or None,
            "timeout": self._config[CONF_TIMEOUT],
        }

        if CONF_USERNAME in self._config:
            username = self._config[CONF_USERNAME]
            password = self._config.get(CONF_PASSWORD, "")
            if self._config.get(CONF_AUTHENTICATION) == HTTP_DIGEST_AUTHENTICATION:
                request_kwargs["middlewares"] = (
                    aiohttp.DigestAuthMiddleware(username, password),
                )
            else:
                request_kwargs["auth"] = aiohttp.BasicAuth(username, password)

        _LOGGER.debug("Calling RESTful Command endpoint with method %s", method)
        try:
            async with getattr(self._websession, method)(
                URL(
                    request_url,
                    encoded=self._config[CONF_SKIP_URL_ENCODING],
                ),
                **request_kwargs,
            ) as response:
                if response.status < HTTPStatus.BAD_REQUEST:
                    _LOGGER.debug(
                        "RESTful Command request succeeded with status code %d",
                        response.status,
                    )
                else:
                    _LOGGER.warning(
                        "RESTful Command request failed with status code %d",
                        response.status,
                    )

                if not return_response:
                    async for _ in response.content.iter_chunked(1024):
                        pass
                    return None

                content = None
                try:
                    if response.content_type == "application/json":
                        content = await response.json()
                    else:
                        content = await response.text()
                except JSONDecodeError, AttributeError:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="decoding_error",
                        translation_placeholders={"decoding_type": "JSON"},
                    ) from None
                except UnicodeDecodeError:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="decoding_error",
                        translation_placeholders={"decoding_type": "text"},
                    ) from None

                return {
                    "content": content,
                    "status": response.status,
                    "headers": {
                        key: values[0] if len(values) == 1 else values
                        for key in response.headers
                        if (values := response.headers.getall(key))
                    },
                }
        except TimeoutError:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="timeout",
            ) from None
        except aiohttp.ClientError, ValueError:
            _LOGGER.error("Error fetching RESTful Command endpoint")
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="client_error",
            ) from None
