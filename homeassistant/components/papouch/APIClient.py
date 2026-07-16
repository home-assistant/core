"""This file is used for communicating with the device."""

# TODO: add other methods of communicating as well (modbus, USB, etc)

import logging

import aiohttp
import defusedxml.ElementTree as ET

from .const import ENCODING

INFO_URL = "is.xml"
DATA_URL = "fresh.xml"
SETTINGS_URL = "settings.xml"
SET_URL = "set.xml"

_LOGGER = logging.getLogger(__name__)


class PapouchApiClient:
    """API client for communicating with a device."""

    def __init__(self, ip_address: str, session: aiohttp.ClientSession) -> None:
        """Constructor for API client."""
        self.base_url = f"http://{ip_address}/"
        self.session = session

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

    async def send_command_GET(self, params: dict) -> None:
        """Command for communicating with any device by using GET request."""

        async with self.session.get(self.base_url + SET_URL, params=params) as response:
            if response.status != 200:
                _LOGGER.error("Failed to send command: %s", response.status)

            self._check_response(await response.text(encoding=ENCODING))

    def _check_response(self, raw_xml):
        """Supposingly every device will use same response status."""
        root = ET.fromstring(raw_xml)

        result_tag = root.find("result")

        if result_tag is not None:
            status = result_tag.attrib.get("status")

            # binary status
            if status == "0":
                # TODO: maybe it would be better to specify what device
                _LOGGER.error("Device returned an error: %s", raw_xml)
                return
        else:
            _LOGGER.error("Response doesn't have result tag!")

    async def get_device_mode(self):
        """Function is used for the resolving the mode of the device."""
        info_xml = await self.fetch_info()
        heartbeat_tag = ET.fromstring(info_xml).find("heartbeat")
        if heartbeat_tag is not None:
            return heartbeat_tag.attrib.get("mode")

        _LOGGER.error("Response doesn't have heartbeat tag!")
        return -1

    async def switch_to_web_mode(self) -> bool:
        """Function that enables WEB mode in the device."""

        raw_xml_info = await self.fetch_info()
        root = ET.fromstring(raw_xml_info)

        # TODO: dodělat
