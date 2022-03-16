"""Configuration for SSDP tests."""
from __future__ import annotations

from collections.abc import Sequence
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlparse

from async_upnp_client.client import UpnpDevice
from async_upnp_client.event_handler import UpnpEventHandler
from async_upnp_client.profiles.igd import StatusInfo
import pytest

from homeassistant.components import ssdp
from homeassistant.components.upnp.const import (
    BYTES_RECEIVED,
    BYTES_SENT,
    CONFIG_ENTRY_ST,
    CONFIG_ENTRY_UDN,
    DOMAIN,
    PACKETS_RECEIVED,
    PACKETS_SENT,
    ROUTER_IP,
    ROUTER_UPTIME,
    WAN_STATUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt

from tests.common import MockConfigEntry

TEST_UDN = "uuid:device"
TEST_ST = "urn:schemas-upnp-org:device:InternetGatewayDevice:1"
TEST_USN = f"{TEST_UDN}::{TEST_ST}"
TEST_LOCATION = "http://192.168.1.1/desc.xml"
TEST_HOSTNAME = urlparse(TEST_LOCATION).hostname
TEST_FRIENDLY_NAME = "mock-name"
TEST_DISCOVERY = ssdp.SsdpServiceInfo(
    ssdp_usn=TEST_USN,
    ssdp_st=TEST_ST,
    ssdp_location=TEST_LOCATION,
    upnp={
        "_udn": TEST_UDN,
        "location": TEST_LOCATION,
        "usn": TEST_USN,
        ssdp.ATTR_UPNP_DEVICE_TYPE: TEST_ST,
        ssdp.ATTR_UPNP_FRIENDLY_NAME: TEST_FRIENDLY_NAME,
        ssdp.ATTR_UPNP_MANUFACTURER: "mock-manufacturer",
        ssdp.ATTR_UPNP_MODEL_NAME: "mock-model-name",
        ssdp.ATTR_UPNP_UDN: TEST_UDN,
    },
    ssdp_headers={
        "_host": TEST_HOSTNAME,
    },
)


class MockUpnpDevice:
    """Mock async_upnp_client UpnpDevice."""

    def __init__(self, location: str) -> None:
        """Initialize."""
        self.device_url = location

    @property
    def manufacturer(self) -> str:
        """Get manufacturer."""
        return TEST_DISCOVERY.upnp[ssdp.ATTR_UPNP_MANUFACTURER]

    @property
    def name(self) -> str:
        """Get name."""
        return TEST_DISCOVERY.upnp[ssdp.ATTR_UPNP_FRIENDLY_NAME]

    @property
    def model_name(self) -> str:
        """Get the model name."""
        return TEST_DISCOVERY.upnp[ssdp.ATTR_UPNP_MODEL_NAME]

    @property
    def device_type(self) -> str:
        """Get the device type."""
        return TEST_DISCOVERY.upnp[ssdp.ATTR_UPNP_DEVICE_TYPE]

    @property
    def udn(self) -> str:
        """Get the UDN."""
        return TEST_DISCOVERY.upnp[ssdp.ATTR_UPNP_UDN]

    @property
    def usn(self) -> str:
        """Get the USN."""
        return f"{self.udn}::{self.device_type}"

    @property
    def unique_id(self) -> str:
        """Get the unique id."""
        return self.usn

    def reinit(self, new_upnp_device: UpnpDevice) -> None:
        """Reinitialize."""
        self.device_url = new_upnp_device.device_url


class MockIgdDevice:
    """Mock async_upnp_client IgdDevice."""

    def __init__(self, device: MockUpnpDevice, event_handler: UpnpEventHandler) -> None:
        """Initialize mock device."""
        self.device = device
        self.profile_device = device

        self._timestamp = dt.utcnow()
        self.traffic_times_polled = 0
        self.status_times_polled = 0

        self.traffic_data = {
            BYTES_RECEIVED: 0,
            BYTES_SENT: 0,
            PACKETS_RECEIVED: 0,
            PACKETS_SENT: 0,
        }
        self.status_data = {
            WAN_STATUS: "Connected",
            ROUTER_UPTIME: 10,
            ROUTER_IP: "8.9.10.11",
        }

    @property
    def name(self) -> str:
        """Get the name of the device."""
        return self.profile_device.name

    @property
    def manufacturer(self) -> str:
        """Get the manufacturer of this device."""
        return self.profile_device.manufacturer

    @property
    def model_name(self) -> str:
        """Get the model name of this device."""
        return self.profile_device.model_name

    @property
    def udn(self) -> str:
        """Get the UDN of the device."""
        return self.profile_device.udn

    @property
    def device_type(self) -> str:
        """Get the device type of this device."""
        return self.profile_device.device_type

    async def async_get_total_bytes_received(self) -> int | None:
        """Get total bytes received."""
        self.traffic_times_polled += 1
        return self.traffic_data[BYTES_RECEIVED]

    async def async_get_total_bytes_sent(self) -> int | None:
        """Get total bytes sent."""
        return self.traffic_data[BYTES_SENT]

    async def async_get_total_packets_received(self) -> int | None:
        """Get total packets received."""
        return self.traffic_data[PACKETS_RECEIVED]

    async def async_get_total_packets_sent(self) -> int | None:
        """Get total packets sent."""
        return self.traffic_data[PACKETS_SENT]

    async def async_get_external_ip_address(
        self, services: Sequence[str] | None = None
    ) -> str | None:
        """
        Get the external IP address.

        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        return self.status_data[ROUTER_IP]

    async def async_get_status_info(
        self, services: Sequence[str] | None = None
    ) -> StatusInfo | None:
        """
        Get status info.

        :param services List of service names to try to get action from, defaults to [WANIPC,WANPPP]
        """
        self.status_times_polled += 1
        return StatusInfo(
            self.status_data[WAN_STATUS], "", self.status_data[ROUTER_UPTIME]
        )


@pytest.fixture(autouse=True)
def mock_upnp_device():
    """Mock homeassistant.components.upnp.Device."""

    async def mock_async_create_upnp_device(
        hass: HomeAssistant, location: str
    ) -> UpnpDevice:
        """Create UPnP device."""
        return MockUpnpDevice(location)

    with patch(
        "homeassistant.components.upnp.device.async_create_upnp_device",
        side_effect=mock_async_create_upnp_device,
    ) as mock_async_create_upnp_device, patch(
        "homeassistant.components.upnp.device.IgdDevice", new=MockIgdDevice
    ) as mock_igd_device:
        yield mock_async_create_upnp_device, mock_igd_device


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
    ) as mock_get_info, patch(
        "homeassistant.components.upnp.config_flow.SSDP_SEARCH_TIMEOUT",
        0.1,
    ):
        yield (mock_register, mock_get_info)


@pytest.fixture
async def config_entry(
    hass: HomeAssistant, mock_get_source_ip, ssdp_instant_discovery, mock_upnp_device
):
    """Create an initialized integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ST: TEST_ST,
        },
    )

    # Load config_entry.
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    yield entry
