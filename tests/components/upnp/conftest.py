"""Configuration for SSDP tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock, create_autospec, patch
from urllib.parse import urlparse

from async_upnp_client.client import UpnpDevice
from async_upnp_client.profiles.igd import IgdDevice, StatusInfo
import pytest

from homeassistant.components import ssdp
from homeassistant.components.upnp.const import (
    CONFIG_ENTRY_LOCATION,
    CONFIG_ENTRY_MAC_ADDRESS,
    CONFIG_ENTRY_ORIGINAL_UDN,
    CONFIG_ENTRY_ST,
    CONFIG_ENTRY_UDN,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_UDN = "uuid:device"
TEST_ST = "urn:schemas-upnp-org:device:InternetGatewayDevice:1"
TEST_USN = f"{TEST_UDN}::{TEST_ST}"
TEST_LOCATION = "http://192.168.1.1/desc.xml"
TEST_HOST = urlparse(TEST_LOCATION).hostname
TEST_FRIENDLY_NAME = "mock-name"
TEST_MAC_ADDRESS = "00:11:22:33:44:55"
TEST_DISCOVERY = ssdp.SsdpServiceInfo(
    ssdp_st=TEST_ST,
    ssdp_udn=TEST_UDN,
    ssdp_usn=TEST_USN,
    ssdp_location=TEST_LOCATION,
    upnp={
        "_udn": TEST_UDN,
        "location": TEST_LOCATION,
        "usn": TEST_USN,
        ssdp.ATTR_UPNP_DEVICE_TYPE: TEST_ST,
        ssdp.ATTR_UPNP_FRIENDLY_NAME: TEST_FRIENDLY_NAME,
        ssdp.ATTR_UPNP_MANUFACTURER: "mock-manufacturer",
        ssdp.ATTR_UPNP_MODEL_NAME: "mock-model-name",
        ssdp.ATTR_UPNP_SERIAL: "mock-serial",
        ssdp.ATTR_UPNP_UDN: TEST_UDN,
    },
    ssdp_headers={
        "_host": TEST_HOST,
    },
)


@pytest.fixture(autouse=True)
def mock_igd_device() -> IgdDevice:
    """Mock async_upnp_client device."""
    mock_upnp_device = create_autospec(UpnpDevice, instance=True)
    mock_upnp_device.device_url = TEST_DISCOVERY.ssdp_location
    mock_upnp_device.serial_number = TEST_DISCOVERY.upnp[ssdp.ATTR_UPNP_SERIAL]

    mock_igd_device = create_autospec(IgdDevice)
    mock_igd_device.device_type = TEST_DISCOVERY.ssdp_st
    mock_igd_device.name = TEST_DISCOVERY.upnp[ssdp.ATTR_UPNP_FRIENDLY_NAME]
    mock_igd_device.manufacturer = TEST_DISCOVERY.upnp[ssdp.ATTR_UPNP_MANUFACTURER]
    mock_igd_device.model_name = TEST_DISCOVERY.upnp[ssdp.ATTR_UPNP_MODEL_NAME]
    mock_igd_device.udn = TEST_DISCOVERY.ssdp_udn
    mock_igd_device.device = mock_upnp_device

    mock_igd_device.async_get_total_bytes_received.return_value = 0
    mock_igd_device.async_get_total_bytes_sent.return_value = 0
    mock_igd_device.async_get_total_packets_received.return_value = 0
    mock_igd_device.async_get_total_packets_sent.return_value = 0
    mock_igd_device.async_get_status_info.return_value = StatusInfo(
        "Connected",
        "",
        10,
    )
    mock_igd_device.async_get_external_ip_address.return_value = "8.9.10.11"

    with patch(
        "homeassistant.components.upnp.device.UpnpFactory.async_create_device"
    ), patch(
        "homeassistant.components.upnp.device.IgdDevice.__new__",
        return_value=mock_igd_device,
    ):
        yield mock_igd_device


@pytest.fixture
def mock_mac_address_from_host():
    """Get mac address."""
    with patch(
        "homeassistant.components.upnp.device.get_mac_address",
        return_value=TEST_MAC_ADDRESS,
    ):
        yield


@pytest.fixture
def mock_no_mac_address_from_host():
    """Get no mac address."""
    with patch(
        "homeassistant.components.upnp.device.get_mac_address",
        return_value=None,
    ):
        yield


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


@pytest.fixture
async def mock_config_entry(
    hass: HomeAssistant,
    mock_get_source_ip,
    ssdp_instant_discovery,
    mock_igd_device: IgdDevice,
    mock_mac_address_from_host,
):
    """Create an initialized integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USN,
        data={
            CONFIG_ENTRY_ST: TEST_ST,
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ORIGINAL_UDN: TEST_UDN,
            CONFIG_ENTRY_LOCATION: TEST_LOCATION,
            CONFIG_ENTRY_MAC_ADDRESS: TEST_MAC_ADDRESS,
        },
    )
    entry.igd_device = mock_igd_device

    # Load config_entry.
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        PropertyMock(return_value=True),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    yield entry
