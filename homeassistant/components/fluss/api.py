"""Fluss+ API Client."""

from __future__ import annotations

import asyncio
import datetime
import logging
import socket
import typing

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

LOGGER = logging.getLogger(__package__)


class FlussApiClientError(Exception):
    """Exception to indicate a general API error."""


class FlussDeviceError(Exception):
    """Exception to indicate that an error occurred when retriveing devices."""


class FlussApiClientCommunicationError(FlussApiClientError):
    """Exception to indicate a communication error."""


class FlussApiClientAuthenticationError(FlussApiClientError):
    """Exception to indicate an authentication error."""


class FlussApiClient:
    """Sample API Client."""

    def __init__(self, api_key: str, hass: HomeAssistant) -> None:
        """Sample API Client."""
        self._api_key = api_key
        self._session = aiohttp_client.async_get_clientsession(hass)

    async def async_get_devices(self) -> typing.Any:
        """Get data from the API."""
        return await self._api_wrapper(
            method="get",
            url="https://zgekzokxrl.execute-api.eu-west-1.amazonaws.com/v1/api/device/list",
            headers={"Authorization": self._api_key},
        )

    async def async_trigger_device(self, deviceId: str) -> typing.Any:
        """Trigger the device."""
        timestamp = int(datetime.datetime.now().timestamp() * 1000)
        return await self._api_wrapper(
            method="post",
            url=f"https://zgekzokxrl.execute-api.eu-west-1.amazonaws.com/v1/api/device/{deviceId}/trigger",
            headers={"Authorization": self._api_key},
            data={"timeStamp": timestamp, "metaData": {}},
        )

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> typing.Any:
        """Get information from the API."""
        try:
            async with asyncio.timeout(10):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                )
                if response.status in (401, 403):
                    raise FlussApiClientAuthenticationError(
                        "Invalid credentials",
                    )
                response.raise_for_status()
                return await response.json()

        except TimeoutError as exception:
            raise FlussApiClientCommunicationError(
                "Timeout error fetching information",
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            raise FlussApiClientCommunicationError(
                "Error fetching information",
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            raise FlussApiClientError("Something really wrong happened!") from exception
