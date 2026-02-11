"""Support for RESTful API."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from aiohttp import hdrs
from multidict import CIMultiDictProxy
import xmltodict

from homeassistant.core import HomeAssistant
from homeassistant.helpers import template
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.json import json_dumps
from homeassistant.util.ssl import SSLCipherList

from .const import XML_MIME_TYPES

DEFAULT_TIMEOUT = 10

_LOGGER = logging.getLogger(__name__)


class RestData:
    """Class for handling the data retrieval."""

    def __init__(
        self,
        hass: HomeAssistant,
        method: str,
        resource: str,
        encoding: str,
        auth: aiohttp.DigestAuthMiddleware | aiohttp.BasicAuth | tuple[str, str] | None,
        headers: dict[str, str] | None,
        params: dict[str, str] | None,
        data: str | None,
        verify_ssl: bool,
        ssl_cipher_list: str,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the data object."""
        self._hass = hass
        self._method = method
        self._resource = resource
        self._encoding = encoding
        self._force_use_set_encoding = False

        # Convert auth tuple to aiohttp.BasicAuth if needed
        if isinstance(auth, tuple) and len(auth) == 2:
            self._auth: aiohttp.BasicAuth | aiohttp.DigestAuthMiddleware | None = (
                aiohttp.BasicAuth(auth[0], auth[1], encoding="utf-8")
            )
        else:
            self._auth = auth

        self._headers = headers
        self._params = params
        self._request_data = data
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._verify_ssl = verify_ssl
        self._ssl_cipher_list = SSLCipherList(ssl_cipher_list)
        self._session: aiohttp.ClientSession | None = None
        self.data: str | None = None
        self.last_exception: Exception | None = None
        self.headers: CIMultiDictProxy[str] | None = None

    def set_payload(self, payload: str) -> None:
        """Set request data."""
        self._request_data = payload

    @property
    def url(self) -> str:
        """Get url."""
        return self._resource

    def set_url(self, url: str) -> None:
        """Set url."""
        self._resource = url

    def _is_expected_content_type(self, content_type: str) -> bool:
        """Check if the content type is one we expect (JSON or XML)."""
        return content_type.startswith(
            ("application/json", "text/json", *XML_MIME_TYPES)
        )

    def data_without_xml(self) -> str | None:
        """If the data is an XML string, convert it to a JSON string."""
        _LOGGER.debug("Data fetched from resource: %s", self.data)
        if (
            (value := self.data) is not None
            # If the http request failed, headers will be None
            and (headers := self.headers) is not None
            and (content_type := headers.get(hdrs.CONTENT_TYPE))
            and content_type.startswith(XML_MIME_TYPES)
        ):
            value = json_dumps(xmltodict.parse(value))
            _LOGGER.debug("JSON converted from XML: %s", value)
        return value

    async def async_update(self, log_errors: bool = True) -> None:
        """Get the latest data from REST service with provided method."""
        if not self._session:
            self._session = async_get_clientsession(
                self._hass,
                verify_ssl=self._verify_ssl,
                ssl_cipher=self._ssl_cipher_list,
            )

        rendered_headers = template.render_complex(self._headers, parse_result=False)
        rendered_params = template.render_complex(self._params)

        # Convert boolean values to lowercase strings for compatibility with aiohttp/yarl
        if rendered_params:
            for key, value in rendered_params.items():
                if isinstance(value, bool):
                    rendered_params[key] = str(value).lower()
                elif not isinstance(value, (str, int, float, type(None))):
                    # For backward compatibility with httpx behavior, convert non-primitive
                    # types to strings. This maintains compatibility after switching from
                    # httpx to aiohttp. See https://github.com/home-assistant/core/issues/148153
                    _LOGGER.debug(
                        "REST query parameter '%s' has type %s, converting to string",
                        key,
                        type(value).__name__,
                    )
                    rendered_params[key] = str(value)

        _LOGGER.debug("Updating from %s", self._resource)
        # Create request kwargs
        request_kwargs: dict[str, Any] = {
            "headers": rendered_headers,
            "params": rendered_params,
            "timeout": self._timeout,
        }

        # Handle authentication
        if isinstance(self._auth, aiohttp.BasicAuth):
            request_kwargs["auth"] = self._auth
        elif isinstance(self._auth, aiohttp.DigestAuthMiddleware):
            request_kwargs["middlewares"] = (self._auth,)

        # Handle data/content
        if self._request_data:
            request_kwargs["data"] = self._request_data
        response = None
        try:
            # Make the request
            async with self._session.request(
                self._method, self._resource, **request_kwargs
            ) as response:
                # Read the response
                # Only use configured encoding if no charset in Content-Type header
                # If charset is present in Content-Type, let aiohttp use it
                if self._force_use_set_encoding is False and response.charset:
                    # Let aiohttp use the charset from Content-Type header
                    try:
                        self.data = await response.text()
                    except UnicodeDecodeError as ex:
                        self._force_use_set_encoding = True
                        _LOGGER.debug(
                            "Response charset came back as %s but could not be decoded, continue with configured encoding %s. %s",
                            response.charset,
                            self._encoding,
                            ex,
                        )
                if self._force_use_set_encoding or not response.charset:
                    # Use configured encoding as fallback
                    self.data = await response.text(encoding=self._encoding)
                self.headers = response.headers

        except TimeoutError as ex:
            if log_errors:
                _LOGGER.error("Timeout while fetching data: %s", self._resource)
            self.last_exception = ex
            self.data = None
            self.headers = None
        except aiohttp.ClientError as ex:
            if log_errors:
                _LOGGER.error(
                    "Error fetching data: %s failed with %s", self._resource, ex
                )
            self.last_exception = ex
            self.data = None
            self.headers = None

        # Log response details outside the try block so we always get logging
        if response is None:
            return

        # Log response details for debugging
        content_type = response.headers.get(hdrs.CONTENT_TYPE)
        _LOGGER.debug(
            "REST response from %s: status=%s, content-type=%s, length=%s",
            self._resource,
            response.status,
            content_type or "not set",
            len(self.data) if self.data else 0,
        )

        # If we got an error response with non-JSON/XML content, log a sample
        # This helps debug issues like servers blocking with HTML error pages
        if (
            response.status >= 400
            and content_type
            and not self._is_expected_content_type(content_type)
        ):
            sample = self.data[:500] if self.data else "<empty>"
            _LOGGER.warning(
                "REST request to %s returned status %s with %s response: %s%s",
                self._resource,
                response.status,
                content_type,
                sample,
                "..." if self.data and len(self.data) > 500 else "",
            )
