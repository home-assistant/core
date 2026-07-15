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

    async def send_command(
        self,
        cmd_type: str,
        item_id: str | None = None,
        counter: str | None = None,
        # sts: str | None = None
    ) -> None:
        """Universal command for communicating with any device by using GET request."""
        # TODO: write into the documentation that HA doesn't support massive setting.

        raw_params = {
            "type": cmd_type,
            "id": item_id,
            "cnt": counter,
            # "sts": sts,
        }

        # adding the optional parameters
        params = {key: value for key, value in raw_params.items() if value is not None}

        async with self.session.get(self.base_url + SET_URL, params=params) as response:
            if response.status != 200:
                _LOGGER.error("Failed to send command to Quido: %s", response.status)

            raw_xml = await response.text(encoding=ENCODING)
            root = ET.fromstring(raw_xml)

            result_tag = root.find("result")

            if result_tag is not None:
                status = result_tag.attrib.get("status")

                if status == "0":
                    _LOGGER.error("Quido returned an error: %s", raw_xml)
                    return
