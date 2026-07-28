"""This file is used for communicating with the device."""

import logging

import aiohttp
import defusedxml.ElementTree as defused_ET

from .exceptions import DeviceConnectionError

INFO_URL = "is.xml"
DATA_URL = "fresh.xml"
SETTINGS_URL = "settings.xml"
SET_URL = "set.xml"
SAVE_URL = "save.xml"

ENCODING = "iso-8859-2"
WEB_MODE_INDEX = 3
TIMEOUT_REQUEST = 10

_LOGGER = logging.getLogger(__name__)


class PapouchApiClient:
    """API client for communicating with a device."""

    def __init__(self, ip_address: str, session: aiohttp.ClientSession) -> None:
        """Constructor for API client."""
        self.base_url = f"http://{ip_address}/"
        self.session = session
        self.ip_address = ip_address

    async def _fetch(self, endpoint: str) -> str:
        async with self.session.get(self.base_url + endpoint) as response:
            response.raise_for_status()
            return await response.text()

    async def fetch_info(self) -> str:
        """Fetching information about a device."""
        return await self._fetch(INFO_URL)

    async def fetch_data(self) -> str:
        """Fetching data about a device."""
        return await self._fetch(DATA_URL)

    async def fetch_settings(self) -> str:
        """Fetching settings about a device."""
        return await self._fetch(SETTINGS_URL)

    async def _send_request(
        self, method: str, endpoint: str, device: str, **kwargs
    ) -> str:

        timeout = aiohttp.ClientTimeout(total=TIMEOUT_REQUEST)

        try:
            async with self.session.request(
                method, self.base_url + endpoint, timeout=timeout, **kwargs
            ) as response:
                if response.status != 200:
                    raise DeviceConnectionError(
                        f"Failed to send command: {response.status}"
                    )
                return await response.text(encoding=ENCODING)

        except (aiohttp.ClientError, TimeoutError) as exception:
            raise DeviceConnectionError(
                f"Failed to connect to {device} - {self.ip_address}: {exception}"
            ) from exception

    async def send_command_GET(self, params: dict, device: str) -> str:
        """Command for communicating with any device by using GET request.

        Parameters are queries that will be added to the request.
        Device string is used for error message.
        """

        return await self._send_request("GET", SET_URL, device, params=params)

    async def send_command_POST(self, data: str, device: str) -> str:
        """Command for communicating with any device by using POST request.

        Data contains the payload that will be sent in the request body.
        Device string is used for error message.
        """

        return await self._send_request("POST", SAVE_URL, device, data=data)

    async def get_device_mode(self) -> int:
        """Function is used for the resolving the mode of the device."""
        info_xml = await self.fetch_info()
        root = defused_ET.fromstring(info_xml)

        heartbeat_tag = None
        for element in root.iter():
            if element.tag.endswith("heartbeat"):
                heartbeat_tag = element
                break

        if heartbeat_tag is not None:
            mode = heartbeat_tag.attrib.get("mode")
            if mode is not None:
                return mode

            # TODO: this is a bad practice but the easiest one
            if heartbeat_tag.attrib.get("device") == "TME":
                return WEB_MODE_INDEX

            _LOGGER.error("Heartbeat tag found, but 'mode' attribute is missing!")
            return -1

        _LOGGER.error("Response doesn't have heartbeat tag!")
        return -1
