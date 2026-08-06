"""This file is used for communicating with the device."""

from abc import ABC, abstractmethod
import logging
import re
from typing import Any, override

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


class PapouchTransport(ABC):
    """Abstract base class for all Papouch communication methods."""

    @abstractmethod
    async def fetch_info(self) -> str:
        """Fetch the device identification data."""

    @abstractmethod
    async def fetch_settings(self) -> str:
        """Fetch the device configuration."""

    @abstractmethod
    async def fetch_data(self) -> str:
        """Fetch the latest sensor readings."""

    @abstractmethod
    async def read_command(
        self, params: dict, context: str, endpoint: str = SET_URL
    ) -> str:
        """Command for communicating with any device by using GET request.

        Parameters are GET queries that will be added to the request.
        Context string is used for error message
        and it will be populated with a device information.
        """

    @abstractmethod
    async def write_command(
        self, payload: str, context: str, endpoint: str = SAVE_URL
    ) -> str:
        """Send a complex payload (like XML settings).

        Context string is used for error message
        and it will be populated with a device information.
        """

    @abstractmethod
    async def get_device_name(self) -> str | None:
        """Return name of the device."""

    @property
    @abstractmethod
    def protocol(self) -> str:
        """Return type of the protocol to communicate with a device."""


class PapouchHTTPClient(PapouchTransport):
    """API client for communicating with a device."""

    def __init__(
        self, ip_address: str, session: aiohttp.ClientSession, password: str = ""
    ) -> None:
        """Constructor for API client."""
        self.base_url = f"http://{ip_address}/"
        self.session = session
        self.ip_address = ip_address

        if password != "":
            self._auth = aiohttp.BasicAuth("admin", password)

        self._auth = aiohttp.BasicAuth("", "")

    @property
    @override
    def protocol(self) -> str:
        return "http"

    async def _fetch(self, endpoint: str) -> str:
        async with self.session.get(
            self.base_url + endpoint, auth=self._auth
        ) as response:
            response.raise_for_status()
            raw_xml = await response.text()
            return re.sub(r'\s+xmlns="[^"]+"', "", raw_xml)

    @override
    async def fetch_info(self) -> str:
        """Fetching information about a device."""
        return await self._fetch(INFO_URL)

    @override
    async def fetch_data(self) -> str:
        """Fetching data about a device."""
        return await self._fetch(DATA_URL)

    @override
    async def fetch_settings(self) -> str:
        """Fetching settings about a device."""
        return await self._fetch(SETTINGS_URL)

    @override
    async def get_device_name(self) -> str | None:
        info = await self.fetch_info()

        try:
            root = defused_ET.fromstring(info)
        except defused_ET.ParseError:
            return None

        heartbeat = None
        for element in root.iter():
            if element.tag.endswith("heartbeat"):
                heartbeat = element
                break

        if heartbeat is None:
            return None

        device = heartbeat.attrib.get("device")
        if not device:
            return None

        return str(device)

    async def _send_request(
        self, method: str, endpoint: str, context: str, **kwargs: Any
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
                f"Failed to connect to {context} - {self.ip_address}: {exception}"
            ) from exception

    @override
    async def read_command(
        self, params: dict, context: str, endpoint: str = SET_URL
    ) -> str:
        """Command for communicating with any device by using GET request.

        Parameters are GET queries that will be added to the request.
        """

        return await self._send_request("GET", endpoint, context, params=params)

    @override
    async def write_command(
        self, payload: str, context: str, endpoint: str = SAVE_URL
    ) -> str:
        """Command for communicating with any device by using POST request.

        Data contains the POST payload that will be sent in the request body.
        Context is a information about the device:

        e.g. f"{self.name} ({self.location})"

        Return response text.
        """

        return await self._send_request("POST", endpoint, context, data=payload)

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
                return int(mode)

            device_name = heartbeat_tag.attrib.get("device")
            if self._check_exceptions_device_web_mode(device_name):
                return WEB_MODE_INDEX

            _LOGGER.error("Heartbeat tag found, but 'mode' attribute is missing!")
            return -1

        _LOGGER.error("Response doesn't have heartbeat tag!")
        return -1

    def _check_exceptions_device_web_mode(self, device_name: str) -> bool:
        if device_name == "TME":
            return True
        if "Papago" in device_name and "ETH" in device_name:
            return True
        return False
