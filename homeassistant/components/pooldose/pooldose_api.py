"""The Seko Pooldose API."""

import asyncio
import logging

import aiohttp
from aiohttp.client_exceptions import ServerDisconnectedError

_LOGGER = logging.getLogger(__name__)


class PooldoseAPIClient:
    """Client for interacting with the Seko Pooldose API."""

    def __init__(self, host, serial_number, timeout, scan_interval) -> None:
        """Initialize the PooldoseAPIClient.

        Args:
            host: The host address of the Pooldose device.
            serial_number: The serial number of the Pooldose device.
            timeout: Timeout for API requests in seconds.
            scan_interval: Interval between scans in seconds.

        """
        self.host = host
        self.serial = serial_number
        self.serial_key = f"{serial_number}_DEVICE"
        self.timeout = timeout
        self.scan_interval = scan_interval
        self._last_data = None

    async def get_instant_values(self):
        """Fetch instant values from the Pooldose device."""
        url = f"http://{self.host}/api/v1/DWI/getInstantValues"
        try:
            async with aiohttp.ClientSession() as session:
                async with asyncio.timeout(self.timeout):
                    async with session.post(url) as response:
                        response.raise_for_status()
                        self._last_data = await response.json()
                        return self._last_data
        except (TimeoutError, ServerDisconnectedError) as e:
            _LOGGER.warning(
                "Pooldose API request failed (%s), using last known good data", e
            )
            if self._last_data is not None:
                return self._last_data
            raise RuntimeError("No cached data available from Pooldose") from e
        except aiohttp.ClientError as e:
            _LOGGER.warning("Client error while fetching pool data: %s", e)
            if self._last_data is not None:
                return self._last_data
            raise RuntimeError(f"Client error fetching pool data: {e}") from e

    async def set_value(self, path, value, type):
        """Set a value on the Pooldose device.

        Args:
            path: The API path to set the value for.
            value: The value to set.
            type: The type of the value (e.g. "STRING", "NUMBER").

        Returns:
            The response from the Pooldose device as a JSON object, or None if an error occurred.

        """
        url = f"http://{self.host}/api/v1/DWI/setInstantValues"
        payload = {
            self.serial_key: {
                path: [
                    {
                        "value": value,
                        "type": type,
                    }
                ]
            }
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with asyncio.timeout(self.timeout):
                    async with session.post(url, json=payload) as response:
                        response.raise_for_status()
        except aiohttp.ClientError as e:
            _LOGGER.warning("Client error setting pool value: %s", e)
        except TimeoutError:
            _LOGGER.warning("Pooldose server timeout during set_value")
