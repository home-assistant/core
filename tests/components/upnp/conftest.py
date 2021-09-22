"""Configuration for SSDP tests."""
from typing import Any, Mapping
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlparse

import pytest

from homeassistant.components import ssdp
from homeassistant.components.upnp.const import (
    BYTES_RECEIVED,
    BYTES_SENT,
    PACKETS_RECEIVED,
    PACKETS_SENT,
    ROUTER_IP,
    ROUTER_UPTIME,
    TIMESTAMP,
    WAN_STATUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt

TEST_UDN = "uuid:device"
TEST_ST = "urn:schemas-upnp-org:device:InternetGatewayDevice:1"
TEST_USN = f"{TEST_UDN}::{TEST_ST}"
TEST_LOCATION = "http://192.168.1.1/desc.xml"
TEST_HOSTNAME = urlparse(TEST_LOCATION).hostname
TEST_FRIENDLY_NAME = "friendly name"
TEST_DISCOVERY = {
    ssdp.ATTR_SSDP_LOCATION: TEST_LOCATION,
    ssdp.ATTR_SSDP_ST: TEST_ST,
    ssdp.ATTR_SSDP_USN: TEST_USN,
    ssdp.ATTR_UPNP_UDN: TEST_UDN,
    "usn": TEST_USN,
    "location": TEST_LOCATION,
    "_host": TEST_HOSTNAME,
    "_udn": TEST_UDN,
    "friendlyName": TEST_FRIENDLY_NAME,
}


class MockDevice:
    """Mock device for Device."""

    def __init__(self, hass: HomeAssistant, udn: str) -> None:
        """Initialize mock device."""
        self.hass = hass
        self._udn = udn
        self.traffic_times_polled = 0
        self.status_times_polled = 0

    @classmethod
    async def async_create_device(cls, hass, ssdp_location) -> "MockDevice":
        """Return self."""
        return cls(hass, TEST_UDN)

    async def async_ssdp_callback(
        self, headers: Mapping[str, Any], change: ssdp.SsdpChange
    ) -> None:
        """SSDP callback, update if needed."""
        pass

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
    def usn(self) -> str:
        """Get the USN."""
        return f"{self.udn}::{self.device_type}"

    @property
    def unique_id(self) -> str:
        """Get the unique id."""
        return self.usn

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
            WAN_STATUS: "Connected",
            ROUTER_UPTIME: 0,
            ROUTER_IP: "192.168.0.1",
        }


@pytest.fixture(autouse=True)
def mock_upnp_device():
    """Mock homeassistant.components.upnp.Device."""
    with patch(
        "homeassistant.components.upnp.Device", new=MockDevice
    ) as mock_async_create_device:
        yield mock_async_create_device


@pytest.fixture
def mock_setup_entry():
    """Mock async_setup_entry."""
    with patch(
        "homeassistant.components.upnp.async_setup_entry",
        return_value=AsyncMock(True),
    ) as mock_setup:
        yield mock_setup


@pytest.fixture(autouse=True)
async def silent_ssdp_scanner(hass):
    """Start SSDP component and get Scanner, prevent actual SSDP traffic."""
    with patch(
        "homeassistant.components.ssdp.Scanner._async_start_ssdp_listeners"
    ), patch("homeassistant.components.ssdp.Scanner._async_stop_ssdp_listeners"), patch(
        "homeassistant.components.ssdp.Scanner.async_scan"
    ):
        yield


@pytest.fixture
async def ssdp_instant_discovery():
    """Instance discovery."""
    # Set up device discovery callback.
    async def register_callback(hass, callback, match_dict):
        """Immediately do callback."""
        await callback(TEST_DISCOVERY, ssdp.SsdpChange.ALIVE)
        return MagicMock()

    with patch(
        "homeassistant.components.ssdp.async_register_callback",
        side_effect=register_callback,
    ) as mock_register, patch(
        "homeassistant.components.ssdp.async_get_discovery_info_by_st",
        return_value=[TEST_DISCOVERY],
    ) as mock_get_info:
        yield (mock_register, mock_get_info)


@pytest.fixture
async def ssdp_no_discovery():
    """No discovery."""
    # Set up device discovery callback.
    async def register_callback(hass, callback, match_dict):
        """Don't do callback."""
        return MagicMock()

    with patch(
        "homeassistant.components.ssdp.async_register_callback",
        side_effect=register_callback,
    ) as mock_register, patch(
        "homeassistant.components.ssdp.async_get_discovery_info_by_st",
        return_value=[],
    ) as mock_get_info:
        yield (mock_register, mock_get_info)
