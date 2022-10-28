"""Maico Data."""
from __future__ import annotations

import logging

import httpx
import xmltodict

from .connection import Connection

# from .sensor import Sensor

LOGGER = logging.getLogger(__name__)


class Maico:
    """Maico Data Class."""

    def __init__(
        self,
        device_name,
        ip,
        websession: httpx.AsyncClient,
        username=None,
        password=None,
    ):
        """Initialize Maico object."""

        self._device_name = device_name
        self._ip = ip
        self._connection = Connection(websession, self._ip)
        self._username = username
        self._password = password
        self._last_update_time = None
        self._is_connected = False

        self._sensors: dict = {}

    async def connect(self):
        """Validate Maico Connection."""
        url = f"http://{self._ip}/index.cgx"
        LOGGER.debug("self._username: %s", self._username)
        results = await self._connection.get(url, self._username, self._password)
        return results.status_code
        # if results.status_code == httpx.codes.OK:
        #     xmltodict.parse(results.text)
        #     return True
        # elif results.status_code == 401:
        #     return False
        # else:
        #     results.raise_for_status()

    async def update(self):
        """Retrieve sensor data and updates the Sensor objects."""
        if not self._is_connected:
            await self.connect()
            self._is_connected = True
        await self._refresh_sensors()

    def get_sensors(self):
        """Get sensor data."""
        return self._sensors

    async def _get_index(self):
        """Retrieve global Status from the Maico."""
        url = f"http://{self._ip}/index.cgx"
        LOGGER.debug("URL: %s", url)
        return await self._connection.get(url, self._username, self._password)

    async def _get_details(self):
        """Retrieve details Status from the Maico."""
        url = f"http://{self._ip}/details.cgx"
        LOGGER.debug("URL: %s", url)
        return await self._connection.get(url, self._username, self._password)

    async def _refresh_sensors(self):
        """Update the Sensor objects."""
        response = await self._get_index()
        LOGGER.debug("Maico index raw_data: %s", response.text)
        index = xmltodict.parse(response.text)
        LOGGER.debug("Maico index: %s", index["form"]["text"])
        index = {value["id"]: value["value"] for value in index["form"]["text"]}

        response = await self._get_details()
        LOGGER.debug("Maico details raw_data: %s", response.text)
        details = xmltodict.parse(response.text)
        LOGGER.debug("Maico details: %s", details["form"]["text"])
        details = {value["id"]: value["value"] for value in details["form"]["text"]}
        self._sensors["sensors"] = index | details
