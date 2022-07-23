"""Sutro API Client."""
from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any

import aiohttp
import async_timeout

TIMEOUT = 10


_LOGGER: logging.Logger = logging.getLogger(__package__)


class SutroApiClient:
    """Sutro API Client library."""

    def __init__(self, token: str, session: aiohttp.ClientSession) -> None:
        """Sample API Client."""
        self._token = token
        self._session = session

    async def async_get_data(self) -> dict | None:
        """Get data from the API."""
        query = """
        {
            me {
                id
                firstName
                device {
                    batteryLevel
                    serialNumber
                    temperature
                }
                pool {
                    latestReading {
                        alkalinity
                        chlorine
                        ph
                        readingTime
                    }
                }
            }
        }
        """
        headers = {
            "Authorization": f"Bearer {self._token}",
        }
        url = "https://api.mysutro.com/graphql"
        response = await self.api_wrapper("post", url, query, headers)
        if response:
            return response["data"]
        return None

    async def api_wrapper(
        self, method: str, url: str, data: Any, headers: dict
    ) -> dict | None:
        """Get information from the API."""
        try:
            async with async_timeout.timeout(TIMEOUT):
                if method == "get":
                    response = await self._session.get(url, headers=headers)
                    return await response.json()

                if method == "post":
                    response = await self._session.post(url, headers=headers, data=data)
                    return await response.json()

                if method == "put":
                    await self._session.put(url, headers=headers, data=data)

                elif method == "patch":
                    await self._session.patch(url, headers=headers, data=data)

        except asyncio.TimeoutError as exception:
            _LOGGER.error(
                "Timeout error fetching information from %s - %s",
                url,
                exception,
            )
        except (KeyError, TypeError) as exception:
            _LOGGER.error(
                "Error parsing information from %s - %s",
                url,
                exception,
            )
        except (aiohttp.ClientError, socket.gaierror) as exception:
            _LOGGER.error(
                "Error fetching information from %s - %s",
                url,
                exception,
            )
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error("Something really wrong happened! - %s", exception)

        return None
