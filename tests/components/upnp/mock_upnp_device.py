"""Mock device for testing purposes."""

from typing import Any, Mapping
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.upnp.const import (
    BYTES_RECEIVED,
    BYTES_SENT,
    PACKETS_RECEIVED,
    PACKETS_SENT,
    TIMESTAMP,
    UPTIME,
    WANIP,
    WANSTATUS,
)
from homeassistant.components.upnp.device import Device
from homeassistant.util import dt

from .common import TEST_UDN


class MockDevice(Device):
    """Mock device for Device."""

    def __init__(self, udn: str) -> None:
        """Initialize mock device."""
        igd_device = object()
        mock_device_updater = AsyncMock()
        super().__init__(igd_device, mock_device_updater)
        self._udn = udn
        self.traffic_times_polled = 0
        self.status_times_polled = 0

    @classmethod
    async def async_create_device(cls, hass, ssdp_location) -> "MockDevice":
        """Return self."""
        return cls(TEST_UDN)

    @property
    def udn(self) -> str:
        """Get the UDN."""
        return self._udn

    @property
    def manufacturer(self) -> str:
        """Get manufacturer."""
        return "mock-manufacturer"

    @property
    def name(self) -> str:
        """Get name."""
        return "mock-name"

    @property
    def model_name(self) -> str:
        """Get the model name."""
        return "mock-model-name"

    @property
    def device_type(self) -> str:
        """Get the device type."""
        return "urn:schemas-upnp-org:device:InternetGatewayDevice:1"

    @property
    def hostname(self) -> str:
        """Get the hostname."""
        return "mock-hostname"

    async def async_get_traffic_data(self) -> Mapping[str, Any]:
        """Get traffic data."""
        self.traffic_times_polled += 1
        return {
            TIMESTAMP: dt.utcnow(),
            BYTES_RECEIVED: 0,
            BYTES_SENT: 0,
            PACKETS_RECEIVED: 0,
            PACKETS_SENT: 0,
        }

    async def async_get_status(self) -> Mapping[str, Any]:
        """Get connection status, uptime, and external IP."""
        self.status_times_polled += 1
        return {
            WANSTATUS: "Connected",
            UPTIME: 0,
            WANIP: "192.168.0.1",
        }

    async def async_start(self) -> None:
        """Start the device updater."""

    async def async_stop(self) -> None:
        """Stop the device updater."""


@pytest.fixture
def mock_upnp_device():
    """Mock upnp Device.async_create_device."""
    with patch(
        "homeassistant.components.upnp.Device", new=MockDevice
    ) as mock_async_create_device:
        yield mock_async_create_device
