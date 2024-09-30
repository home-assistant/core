"""Support for a Appartme PaaS API."""

import logging
from typing import Any

from aiohttp import ClientSession

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_URL

_LOGGER = logging.getLogger(__name__)


class DeviceOfflineError(Exception):
    """Exception raised when a device is offline."""


class AppartmeCloudAPI:
    """Class to communicate with the Appartme Cloud API."""

    def __init__(self, hass, token):
        """Initialize the Appartme API."""
        self.base_url = API_URL
        self.token = token
        self.session: ClientSession = async_get_clientsession(hass)

    async def fetch_devices(self) -> dict[str, Any] | None:
        """Fetch the list of devices."""
        url = f"{self.base_url}/devices"
        headers = {"Authorization": f"Bearer {self.token['access_token']}"}
        session = self.session

        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                error_message = await response.text()
                _LOGGER.error(
                    "Error fetching devices: %s, %s", response.status, error_message
                )
                return None
            return await response.json()

    async def fetch_device_details(self, device_id: str) -> dict[str, Any] | None:
        """Fetch the details of a specific device."""
        url = f"{self.base_url}/devices/{device_id}"
        headers = {"Authorization": f"Bearer {self.token['access_token']}"}
        session = self.session

        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                error_message = await response.text()
                raise ValueError(
                    f"Error fetching device details for {device_id}: {error_message}"
                )
            return await response.json()

    async def set_device_property_value(
        self, device_id: str, property: str, value: Any
    ) -> dict[str, Any] | None:
        """Control device property."""
        url = f"{self.base_url}/devices/{device_id}/property/{property}/value"
        headers = {"Authorization": f"Bearer {self.token['access_token']}"}
        payload = {"value": value}
        session = self.session

        async with session.patch(url, headers=headers, json=payload) as response:
            if response.status == 504:
                raise DeviceOfflineError(
                    f"Property {property} control error. Device {device_id} is offline"
                )
            if response.status != 200:
                error_message = await response.text()
                raise HomeAssistantError(f"API Error: {error_message}")
            return await response.json()

    async def get_device_property_value(
        self, device_id: str, property: str
    ) -> dict[str, Any] | None:
        """Fetch device property value."""
        url = f"{self.base_url}/devices/{device_id}/property/{property}/value"
        headers = {"Authorization": f"Bearer {self.token['access_token']}"}
        session = self.session

        async with session.get(url, headers=headers) as response:
            if response.status == 504:
                raise DeviceOfflineError(
                    f"Property {property} fetch error. Device {device_id} is offline"
                )
            if response.status != 200:
                error_message = await response.text()
                raise HomeAssistantError(f"API Error: {error_message}")
            return await response.json()

    async def get_device_properties(self, device_id: str) -> dict[str, Any] | None:
        """Fetch all device property values."""
        url = f"{self.base_url}/devices/{device_id}/property"
        headers = {"Authorization": f"Bearer {self.token['access_token']}"}
        session = self.session

        async with session.get(url, headers=headers) as response:
            if response.status == 504:
                raise DeviceOfflineError(
                    f"Property fetch error. Device {device_id} is offline"
                )
            if response.status != 200:
                error_message = await response.text()
                raise HomeAssistantError(f"API Error: {error_message}")
            return await response.json()
