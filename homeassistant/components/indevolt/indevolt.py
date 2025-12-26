"""Indevolt OpenData API."""

from http import HTTPStatus
import json
import logging
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 8080

KEYS_GEN1 = [
    7101,
    1664,
    1665,
    2108,
    1502,
    1505,
    2101,
    2107,
    1501,
    6000,
    6001,
    6002,
    6105,
    6004,
    6005,
    6006,
    6007,
    7120,
    21028,
]

KEYS_GEN2 = [
    7101,
    1664,
    1665,
    1666,
    1667,
    1501,
    2108,
    1502,
    1505,
    2101,
    2107,
    142,
    6000,
    6001,
    6009,
    6105,
    6004,
    6005,
    6006,
    6007,
    7120,
    11016,
    667,
]


class Indevolt:
    """API client for interacting with Indevolt devices."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        port: int = DEFAULT_PORT,
    ) -> None:
        """Initialize indevolt API client.

        :param session: aiohttp client session
        :param host: Device hostname or IP address
        :param port: Device port (default: 8080)
        """
        self.host = host
        self.port = port
        self.session = session
        self.base_url = f"http://{host}:{port}/rpc"

    async def fetch_data(
        self, key: int, timeout: ClientTimeout = ClientTimeout(30)
    ) -> dict[str, Any]:
        """Fetch a single JSON value from the device."""
        config_param = json.dumps({"t": [key]}).replace(" ", "")
        url = f"{self.base_url}/Indevolt.GetData?config={config_param}"

        _LOGGER.debug("Sending request to %s", url)

        try:
            async with self.session.post(url=url, timeout=timeout) as resp:
                data = await resp.json()
                _LOGGER.debug(
                    "Received response: Status %d. Response data: %s",
                    resp.status,
                    json.dumps(data, indent=2),
                )

                validate_response(HTTPStatus(resp.status))

                return data

        except TimeoutError as err:
            raise DeviceConnectionError(
                f"Timeout connecting to {self.host}:{self.port}"
            ) from err
        except ClientError as err:
            raise DeviceConnectionError(
                f"Connection error to {self.host}:{self.port} {err}"
            ) from err
        except Exception as err:
            raise DeviceResponseError(f"Unexpected error: {err}") from err

    async def fetch_all_data(
        self, keys: list, timeout: ClientTimeout = ClientTimeout(30)
    ) -> dict[str, Any]:
        """Fetch all JSON data from the device."""
        data: dict[str, Any] = {}

        for key in keys:
            result = await self.fetch_data(key, timeout=timeout)
            data.update(result)

        return data


class DeviceConnectionError(Exception):
    """Exception for device connection issues."""


class DeviceResponseError(Exception):
    """Exception for invalid device responses."""


def validate_response(status: HTTPStatus) -> bool:
    """Validate API response status and content."""
    if status != HTTPStatus.OK:
        raise DeviceResponseError(f"Unexpected status: {status}.")

    return True
