"""Solarman OpenData API."""

from http import HTTPStatus
import json
import logging

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30


class Solarman:
    """API client for interacting with Solarman devices."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        port: int = DEFAULT_PORT,
        headers: dict | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize Solarman API client.

        :param session: aiohttp client session
        :param host: Device hostname or IP address
        :param port: Device port (default: 8080)
        :param headers: Default request headers
        :param timeout: Request timeout in seconds
        """
        self.session = session
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}/rpc"
        self.headers = headers
        self.timeout = ClientTimeout(total=timeout)
        self.device_type = None

        self.headers = {"name": "opend", "pass": "opend"}

    async def request(
        self,
        method: str,
        api: str,
        params: dict | None = None,
        timeout: ClientTimeout | None = None,
    ) -> tuple[HTTPStatus, dict]:
        """Make an API request."""
        url = f"{self.base_url}/{api}"
        _LOGGER.debug("Sending %s request to %s", method, url)

        try:
            async with self.session.request(
                method=method,
                url=url,
                params=params,
                headers=self.headers,
                raise_for_status=True,
                timeout=timeout or self.timeout,
            ) as resp:
                data = await resp.json()
                _LOGGER.debug(
                    "Received response: Status %d. Response data: %s",
                    resp.status,
                    json.dumps(data, indent=2),
                )
                return (HTTPStatus(resp.status), data)

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

    async def fetch_data(self) -> dict:
        """Get real-time device data."""

        api_map = {
            "SP-2W-EU": "Plug.GetData",
            "P1-2W": "P1.JsonData",
            "gl meter": "Meter.JsonData",
        }

        device_type = self.device_type

        if device_type is None:
            # Obtain device model.
            config_data = await get_config(
                self.session, self.host, self.port, self.timeout
            )
            if config_data.get("device") is None:
                device_type = config_data.get("type")
            else:
                device_type = config_data["device"].get("type")

            if device_type is None:
                return {}

            self.device_type = device_type

        # Fetch data.
        api = api_map.get(device_type)
        if api is None:
            return {}

        status, data = await self.request("GET", api)
        validate_response(status)

        # Obtain device status.
        status_data = await self.get_status()
        data.update(status_data)

        return data

    async def get_status(self) -> dict:
        """Get plug status."""
        if self.device_type != "SP-2W-EU":
            return {}

        status, data = await self.request("GET", "Plug.GetStatus")
        validate_response(status)
        return data

    async def set_status(self, active: bool):
        """Set the switch state of a smart plug.

        :param active: True to turn on, False to turn off
        :return: True if successful
        """
        if self.device_type != "SP-2W-EU":
            return

        switch_status = "on" if active else "off"
        config_param = json.dumps({"switch_status": switch_status}).replace(" ", "")
        payload = {"config": config_param}

        status, response = await self.request("POST", "Plug.SetStatus", payload)
        validate_response(status)

        if not response["result"]:
            _LOGGER.error(
                "Failed to set switch state: Status %d, Response: %s", status, response
            )


class DeviceConnectionError(Exception):
    """Exception for device connection issues."""


class DeviceResponseError(Exception):
    """Exception for invalid device responses."""


async def get_config(
    session: ClientSession,
    host: str,
    port: int = DEFAULT_PORT,
    timeout=ClientTimeout(total=DEFAULT_TIMEOUT),
) -> dict:
    """Get device configuration."""
    url = f"http://{host}:{port}/rpc/Sys.GetConfig"

    headers = {"name": "opend", "pass": "opend"}

    try:
        async with session.get(
            url,
            headers=headers,
            raise_for_status=True,
            timeout=timeout,
        ) as resp:
            data = await resp.json()
            validate_response(HTTPStatus(resp.status))
            return data

    except TimeoutError as err:
        raise DeviceConnectionError(f"Timeout connecting to {host}:{port}") from err
    except ClientError as err:
        raise DeviceConnectionError(f"Connection error to {host}:{port} {err}") from err
    except Exception as err:
        raise DeviceResponseError(f"Unexpected error: {err}") from err


def validate_response(status: HTTPStatus) -> bool:
    """Validate API response status and content."""
    if status != HTTPStatus.OK:
        raise DeviceResponseError(f"Unexpected status: {status}.")

    return True
