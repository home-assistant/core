"""Support for RESTful API."""
import json
import logging
from xml.parsers.expat import ExpatError

import httpx
import xmltodict

from homeassistant.components.rest.utils import render_templates
from homeassistant.helpers.httpx_client import get_async_client

DEFAULT_TIMEOUT = 10

_LOGGER = logging.getLogger(__name__)


class RestData:
    """Class for handling the data retrieval."""

    def __init__(
        self,
        hass,
        method,
        resource,
        auth,
        headers,
        params,
        data,
        verify_ssl,
        timeout=DEFAULT_TIMEOUT,
    ):
        """Initialize the data object."""
        self._hass = hass
        self._method = method
        self._resource = resource
        self._auth = auth
        self._headers = headers
        self._params = params
        self._request_data = data
        self._timeout = timeout
        self._verify_ssl = verify_ssl
        self._async_client = None
        self.data = None
        self.last_exception = None
        self.headers = None

    def set_url(self, url):
        """Set url."""
        self._resource = url

    async def async_update(self, log_errors=True):
        """Get the latest data from REST service with provided method."""
        if not self._async_client:
            self._async_client = get_async_client(
                self._hass, verify_ssl=self._verify_ssl
            )

        rendered_headers = render_templates(self._headers)
        rendered_params = render_templates(self._params)

        _LOGGER.debug("Updating from %s", self._resource)
        try:
            response = await self._async_client.request(
                self._method,
                self._resource,
                headers=rendered_headers,
                params=rendered_params,
                auth=self._auth,
                data=self._request_data,
                timeout=self._timeout,
            )
            self.data = response.text
            self.headers = response.headers
        except httpx.RequestError as ex:
            if log_errors:
                _LOGGER.error(
                    "Error fetching data: %s failed with %s", self._resource, ex
                )
            self.last_exception = ex
            self.data = None
            self.headers = None

        if self.headers is not None:
            # If the http request failed, headers will be None
            content_type = self.headers.get("content-type")

            if content_type and (
                content_type.startswith("text/xml")
                or content_type.startswith("application/xml")
                or content_type.startswith("application/xhtml+xml")
            ):
                try:
                    value = json.dumps(xmltodict.parse(self.data))
                    _LOGGER.debug("JSON converted from XML: %s", self.data)
                    self.data = value
                except ExpatError:
                    _LOGGER.warning(
                        "REST xml result could not be parsed and converted to JSON"
                    )
                    _LOGGER.debug("Erroneous XML: %s", self.data)
