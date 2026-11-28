"""Mock Hinen API for testing."""

from collections.abc import AsyncGenerator
from typing import Any

from hinen_open_api.models import HinenDeviceControl, HinenDeviceDetail, HinenDeviceInfo
from pytest_homeassistant.common import async_load_json_array_fixture

from homeassistant.components.hinen_power.const import DOMAIN, PROPERTIES
from homeassistant.core import HomeAssistant


class MockHinen:
    """Service which returns mock objects."""

    _thrown_error: Exception | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        devices_fixture: str = "get_devices.json",
    ) -> None:
        """Initialize MockHinen."""
        self.hass = hass
        self.device_fixture = devices_fixture

    async def set_user_authentication(
        self,
        token: str,
        refresh_token: str | None = None,
    ) -> None:
        """Authenticate the user."""

    async def get_device_infos(self) -> AsyncGenerator[HinenDeviceInfo]:
        """Mock get device infos."""
        if self.device_fixture == "get_no_device.json":
            return

        # Return mock device info
        device_info = await async_load_json_array_fixture(
            self.hass, self.device_fixture, DOMAIN
        )
        for item in device_info:
            yield HinenDeviceInfo(**item)

    async def get_device_details(
        self,
        device_ids: list[str],
    ) -> AsyncGenerator[HinenDeviceDetail]:
        """Mock get device details."""
        # Return mock device info
        device_detail = await async_load_json_array_fixture(
            self.hass, "get_device_detail.json", DOMAIN
        )
        for item in device_detail:
            yield HinenDeviceDetail(**item)

    async def set_property(self, value: Any, device_id: str, key: str) -> None:
        """Mock Set property."""
        property_identifier = PROPERTIES.get(key)
        if property_identifier is None:
            raise ValueError(f"Unknown property key: {key}")
        HinenDeviceControl(deviceId=device_id, map={property_identifier: value})

    def set_thrown_exception(self, exception: Exception) -> None:
        """Set thrown exception for testing purposes."""
        self._thrown_error = exception
