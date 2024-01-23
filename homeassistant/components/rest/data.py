"""Support for RESTful API."""
from __future__ import annotations

import logging
import ssl
from xml.parsers.expat import ExpatError

import httpx
import xmltodict

from homeassistant.core import HomeAssistant
from homeassistant.helpers import template
from homeassistant.helpers.httpx_client import create_async_httpx_client
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
        auth: httpx.DigestAuth | tuple[str, str] | None,
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
        self._auth = auth
        self._headers = headers
        self._params = params
        self._request_data = data
        self._timeout = timeout
        self._verify_ssl = verify_ssl
        self._ssl_cipher_list = SSLCipherList(ssl_cipher_list)
        self._async_client: httpx.AsyncClient | None = None
        self.data: str | None = None
        self.last_exception: Exception | None = None
        self.headers: httpx.Headers | None = None

    @property
    def url(self) -> str:
        """Get url."""
        return self._resource

    def set_url(self, url: str) -> None:
        """Set url."""
        self._resource = url

    def data_without_xml(self) -> str | None:
        """If the data is an XML string, convert it to a JSON string."""
        _LOGGER.debug("Data fetched from resource: %s", self.data)
        if (
            (value := self.data) is not None
            # If the http request failed, headers will be None
            and (headers := self.headers) is not None
            and (content_type := headers.get("content-type"))
            and content_type.startswith(XML_MIME_TYPES)
        ):
            try:
                value = json_dumps(xmltodict.parse(value))
            except ExpatError:
                _LOGGER.warning(
                    "REST xml result could not be parsed and converted to JSON"
                )
            else:
                _LOGGER.debug("JSON converted from XML: %s", value)
        return value

    async def async_update(self, log_errors: bool = True) -> None:
        """Get the latest data from REST service with provided method."""
        if not self._async_client:
            self._async_client = create_async_httpx_client(
                self._hass,
                verify_ssl=self._verify_ssl,
                default_encoding=self._encoding,
                ssl_cipher_list=self._ssl_cipher_list,
            )

        rendered_headers = template.render_complex(self._headers, parse_result=False)
        rendered_params = template.render_complex(self._params)

        _LOGGER.debug("Updating from %s", self._resource)
        try:
            response = await self._async_client.request(
                self._method,
                self._resource,
                headers=rendered_headers,
                params=rendered_params,
                auth=self._auth,
                content=self._request_data,
                timeout=self._timeout,
                follow_redirects=True,
            )
            self.data = response.text
            self.headers = response.headers
        except httpx.TimeoutException as ex:
            if log_errors:
                _LOGGER.error("Timeout while fetching data: %s", self._resource)
            self.last_exception = ex
            self.data = None
            self.headers = None
        except httpx.RequestError as ex:
            if log_errors:
                _LOGGER.error(
                    "Error fetching data: %s failed with %s", self._resource, ex
                )
            self.last_exception = ex
            self.data = None
            self.headers = None
        except ssl.SSLError as ex:
            if log_errors:
                _LOGGER.error(
                    "Error connecting to %s failed with %s", self._resource, ex
                )
            self.last_exception = ex
            self.data = None
            self.headers = None
