"""Common for upnp."""

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
    TIMESTAMP,
)
from homeassistant.components.upnp.device import Device
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
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


class MockDevice(Device):
    """Mock device for Device."""

    def __init__(self, udn: str) -> None:
        """Initialize mock device."""
        igd_device = object()
        mock_device_updater = AsyncMock()
        super().__init__(igd_device, mock_device_updater)
        self._udn = udn
        self.times_polled = 0

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
        self.times_polled += 1
        return {
            TIMESTAMP: dt.utcnow(),
            BYTES_RECEIVED: 0,
            BYTES_SENT: 0,
            PACKETS_RECEIVED: 0,
            PACKETS_SENT: 0,
        }

    async def async_start(self) -> None:
        """Start the device updater."""

    async def async_stop(self) -> None:
        """Stop the device updater."""


@pytest.fixture
def mock_upnp_device():
    """Mock homeassistant.components.upnp.Device."""
    with patch(
        "homeassistant.components.upnp.Device", new=MockDevice
    ) as mock_async_create_device:
        yield mock_async_create_device


@pytest.fixture
async def ssdp_listener(hass: HomeAssistant):
    """Start SSDP component and get SsdpListener, prevent actual SSDP traffic."""
    with patch("homeassistant.components.ssdp.SsdpListener.async_start"), patch(
        "homeassistant.components.ssdp.SsdpListener.async_stop"
    ), patch("homeassistant.components.ssdp.SsdpListener.async_search"):
        await async_setup_component(hass, ssdp.DOMAIN, {ssdp.DOMAIN: {}})
        await hass.async_block_till_done()
        yield hass.data[ssdp.DOMAIN]._ssdp_listeners[0]


@pytest.fixture
async def ssdp_instant_discovery():
    """Instance discovery."""
    # Set up device discovery callback.
    async def register_callback(hass, callback, match_dict):
        """Immediately do callback."""
        await callback(TEST_DISCOVERY, ssdp.SsdpChange.ALIVE)
        return MagicMock()

    async def get_discovery_info(hass, st):
        """Return discovery info."""
        return [TEST_DISCOVERY]

    with patch(
        "homeassistant.components.ssdp.async_register_callback",
        side_effect=register_callback,
    ) as mock_register, patch(
        "homeassistant.components.ssdp.async_get_discovery_info_by_st",
        side_effect=get_discovery_info,
    ) as mock_get_info:
        yield (mock_register, mock_get_info)


@pytest.fixture
async def ssdp_no_discovery():
    """No discovery."""
    # Set up device discovery callback.
    async def register_callback(hass, callback, match_dict):
        """Don't do callback."""
        return MagicMock()

    async def get_discovery_info(hass, st):
        """Return no discovery infos."""
        return []

    with patch(
        "homeassistant.components.ssdp.async_register_callback",
        side_effect=register_callback,
    ) as mock_register, patch(
        "homeassistant.components.ssdp.async_get_discovery_info_by_st",
        side_effect=get_discovery_info,
    ) as mock_get_info:
        yield (mock_register, mock_get_info)
