"""Common code go-e Charger integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

import aiohttp
import asyncio
import async_timeout
import json
import urllib.parse

_LOGGER = logging.getLogger(__name__)


class GoeChargerHub:
    def __init__(self, secure: bool, host: str, pathprefix: str) -> None:
        """Initialize."""
        self._secure = secure
        self._host = host
        self._pathprefix = pathprefix

    def get_urlbase(self):
        url = 'http'
        if self._secure:
            url += 's'
        url += '://' + self._host + self._pathprefix

        return url

    async def get_data(self, hass: HomeAssistant, keys: list[str]) -> bool:
        """Get the data from the charger."""

        url = self.get_urlbase() + '/api/status?filter=' + urllib.parse.quote_plus(','.join(keys))

        session = async_get_clientsession(hass)

        try:
            with async_timeout.timeout(10):
                resp = await session.get(url)
                content = await resp.text()
        except asyncio.TimeoutError:
            _LOGGER.warning("Request timeout")
            raise TimeoutOccured(url)
        except aiohttp.ClientError:
            _LOGGER.warning("Request exception")
            raise CannotConnect(url)

        if resp.status != 200:
            _LOGGER.warning("Request invalid response %i %s", resp.status, content)
            raise InvalidRespStatus(resp.status, content)

        try:
            parsed = json.loads(content)
        except Exception as e:  # pylint: disable=broad-except
            details = "Could not parse json " + str(e)
            _LOGGER.warning("%s %s", details, content)
            raise InvalidJson(details, content)

        if type(parsed) is not dict:
            details = "json is not a dict ({})".format(type(parsed).__name__)
            _LOGGER.warning("%s", details)
            raise InvalidJson(details, content)

        for key in keys:
            if key not in parsed:
                details = key + " not set in json object"
                _LOGGER.warning("%s", details)
                raise InvalidJson(details, content)

        _LOGGER.debug("Data received successfully for %s!", self._host)

        return parsed

    async def set_data(self, hass: HomeAssistant, data: dict[str, Any]) -> None:
        """Set data to the charger."""

        url = self.get_urlbase() + '/api/set?'
        for key, value in data.items():
            url += urllib.parse.quote_plus(key) + '=' + urllib.parse.quote_plus(json.dumps(value)) + '&'

        session = async_get_clientsession(hass)

        try:
            with async_timeout.timeout(10):
                resp = await session.get(url)
                content = await resp.text()
        except asyncio.TimeoutError:
            _LOGGER.warning("Request timeout")
            raise TimeoutOccured(url)
        except aiohttp.ClientError:
            _LOGGER.warning("Request exception")
            raise CannotConnect(url)

        if resp.status != 200:
            _LOGGER.warning("Request invalid response %i %s", resp.status, content)
            raise InvalidRespStatus(resp.status, content)

        try:
            parsed = json.loads(content)
        except Exception as e:  # pylint: disable=broad-except
            details = "Could not parse json " + str(e)
            _LOGGER.warning("%s %s", details, content)
            raise InvalidJson(details, content)

        if type(parsed) is not dict:
            details = "json is not a dict ({})".format(type(parsed).__name__)
            _LOGGER.warning("%s", details)
            raise InvalidJson(details, content)

        for key in data:
            if key not in parsed:
                details = key + " not set in json object"
                _LOGGER.warning("%s", details)
                raise InvalidJson(details, content)

            if parsed[key] != True:
                details = key + parsed[key]
                _LOGGER.warning("%s", details)
                raise InvalidJson(details, content)

        _LOGGER.debug("Data set successfully for %s!", self._host)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

    def __init__(self, url: str) -> None:
        """Initialize."""
        self.url = url


class TimeoutOccured(HomeAssistantError):
    """Error to indicate we cannot connect."""

    def __init__(self, url: str) -> None:
        """Initialize."""
        self.url = url


class InvalidRespStatus(HomeAssistantError):
    """Error to indicate we got an invalid response status."""

    def __init__(self, status: int, response: str) -> None:
        """Initialize."""
        self.status = status
        self.response = response


class InvalidJson(HomeAssistantError):
    """Error to indicate we got an invalid json response."""

    def __init__(self, details: str, response: str) -> None:
        """Initialize."""
        self.details = details
        self.response = response


class NotImplemented(HomeAssistantError):
    """Error to indicate that something is not yet implemented."""
