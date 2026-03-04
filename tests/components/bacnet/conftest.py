"""Common fixtures for the BACnet tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.bacnet.bacnet_client import (
    BACnetDeviceInfo,
    BACnetObjectInfo,
)

from . import MOCK_DEVICE_ADDRESS, MOCK_DEVICE_ID

# Map of (object_type, object_instance) -> present_value for polling
MOCK_PRESENT_VALUES: dict[tuple[str, int], Any] = {
    ("analog-input", 0): 72.5,
    ("analog-input", 1): 55.0,
    ("analog-input", 2): 45.0,
    ("analog-output", 0): 75.0,
    ("analog-value", 0): 72.0,
    ("binary-input", 0): 1,
    ("binary-input", 1): 0,
    ("binary-output", 0): 1,
    ("binary-value", 0): 0,
    ("multi-state-input", 0): 2,
    ("multi-state-output", 0): 1,
}


def _create_mock_device_info() -> BACnetDeviceInfo:
    """Create a mock BACnet device info."""
    return BACnetDeviceInfo(
        device_id=MOCK_DEVICE_ID,
        address=MOCK_DEVICE_ADDRESS,
        name="Test HVAC Controller",
        vendor_name="Test Vendor",
        model_name="Model X",
        firmware_revision="1.0.0",
        description="A test BACnet device",
    )


def _create_mock_objects() -> list[BACnetObjectInfo]:
    """Create a list of mock BACnet objects."""
    return [
        BACnetObjectInfo(
            object_type="analog-input",
            object_instance=0,
            object_name="Zone Temperature",
            present_value=72.5,
            units="degreesFahrenheit",
            description="Zone 1 temperature sensor",
        ),
        BACnetObjectInfo(
            object_type="analog-input",
            object_instance=1,
            object_name="Outside Air Temperature",
            present_value=55.0,
            units="degreesFahrenheit",
            description="Outside air temperature sensor",
        ),
        BACnetObjectInfo(
            object_type="analog-input",
            object_instance=2,
            object_name="Zone Humidity",
            present_value=45.0,
            units="percentRelativeHumidity",
            description="Zone 1 humidity sensor",
        ),
        BACnetObjectInfo(
            object_type="analog-output",
            object_instance=0,
            object_name="Heating Valve",
            present_value=75.0,
            units="percent",
            description="Heating valve position",
        ),
        BACnetObjectInfo(
            object_type="analog-value",
            object_instance=0,
            object_name="Setpoint",
            present_value=72.0,
            units="degreesFahrenheit",
            description="Zone temperature setpoint",
        ),
        BACnetObjectInfo(
            object_type="binary-input",
            object_instance=0,
            object_name="Occupancy Sensor",
            present_value=1,
            units="",
            description="Zone occupancy status",
        ),
        BACnetObjectInfo(
            object_type="binary-input",
            object_instance=1,
            object_name="Filter Status",
            present_value=0,
            units="",
            description="Air filter status",
        ),
        BACnetObjectInfo(
            object_type="binary-output",
            object_instance=0,
            object_name="Fan Command",
            present_value=1,
            units="",
            description="Supply fan command",
        ),
        BACnetObjectInfo(
            object_type="binary-value",
            object_instance=0,
            object_name="Alarm Active",
            present_value=0,
            units="",
            description="System alarm status",
        ),
        BACnetObjectInfo(
            object_type="multi-state-input",
            object_instance=0,
            object_name="Operating Mode",
            present_value=2,
            units="",
            description="Current operating mode",
            state_text=["Off", "Heating", "Cooling", "Auto"],
        ),
        BACnetObjectInfo(
            object_type="multi-state-output",
            object_instance=0,
            object_name="Fan Speed",
            present_value=1,
            units="",
            description="Fan speed selection",
            state_text=["Low", "Medium", "High"],
        ),
    ]


async def _mock_read_present_value(
    address: str, object_type: str, object_instance: int
) -> Any:
    """Return mock present values based on the object being read."""
    return MOCK_PRESENT_VALUES.get((object_type, object_instance), 0)


@pytest.fixture
def mock_bacnet_client() -> Generator[AsyncMock]:
    """Mock a BACnet client."""
    device_info = _create_mock_device_info()
    objects = _create_mock_objects()

    with patch(
        "homeassistant.components.bacnet.BACnetClient",
        autospec=True,
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.connected = True
        client.connect = AsyncMock()
        client.disconnect = AsyncMock()

        async def _mock_discover_devices(
            timeout: int = 5,
            low_limit: int | None = None,
            high_limit: int | None = None,
        ) -> list:
            """Return device for targeted discovery, empty for broadcast.

            Targeted discovery (with low_limit/high_limit) returns the mock
            device when its ID is in range. Broadcast discovery (no limits)
            returns empty to prevent auto-add reloads in most tests.
            """
            if low_limit is not None:
                if low_limit <= device_info.device_id <= (high_limit or low_limit):
                    return [device_info]
                return []
            return []

        client.discover_devices = AsyncMock(side_effect=_mock_discover_devices)
        client.discover_device_at_address = AsyncMock(return_value=device_info)
        client.get_device_objects = AsyncMock(return_value=objects)
        client.read_present_value = AsyncMock(side_effect=_mock_read_present_value)
        client.write_present_value = AsyncMock()
        client.subscribe_cov = AsyncMock(
            side_effect=lambda addr, obj_type, obj_inst, cb: (
                f"{addr}:{obj_type},{obj_inst}"
            )
        )
        client.unsubscribe_cov = AsyncMock()

        yield client


@pytest.fixture
def mock_get_local_interfaces() -> Generator[AsyncMock]:
    """Mock get_local_interfaces function."""
    with patch(
        "homeassistant.components.bacnet.config_flow.get_local_interfaces",
        autospec=True,
    ) as mock_get_interfaces:
        # Return interface names as keys, subnet range as values
        mock_get_interfaces.return_value = {
            "eth0": "eth0 192.168.21.0-192.168.21.255",
            "wlan0": "wlan0 10.0.0.0-10.0.0.255",
            "manual": "Enter IP address manually...",
        }
        yield mock_get_interfaces


@pytest.fixture
def mock_resolve_interface_to_ip() -> Generator[AsyncMock]:
    """Mock resolve_interface_to_ip function."""

    async def _resolve(interface: str) -> str:
        """Resolve interface to IP."""
        if interface == "eth0":
            return "192.168.21.223"
        # For 0.0.0.0, manual, or actual IPs, return as-is
        return interface

    with patch(
        "homeassistant.components.bacnet.resolve_interface_to_ip",
        side_effect=_resolve,
    ):
        yield
