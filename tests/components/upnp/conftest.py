"""Configuration for SSDP tests."""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Generator
import copy
from datetime import datetime
import socket
from typing import Any
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch
from urllib.parse import urlparse

from async_upnp_client.aiohttp import AiohttpNotifyServer
from async_upnp_client.client import UpnpDevice
from async_upnp_client.profiles.igd import IgdDevice, IgdState
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
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_SERIAL,
    SsdpServiceInfo,
)

from tests.common import MockConfigEntry, load_ssdp_fixture

TEST_UDN = "uuid:device"
TEST_ST = "urn:schemas-upnp-org:device:InternetGatewayDevice:1"
TEST_USN = f"{TEST_UDN}::{TEST_ST}"
TEST_LOCATION = "http://192.168.1.1/desc.xml"
TEST_LOCATION6 = "http://[fe80::1%2]/desc.xml"
TEST_HOST = urlparse(TEST_LOCATION).hostname
TEST_FRIENDLY_NAME = "mock-name"
TEST_MAC_ADDRESS = "00:11:22:33:44:55"
TEST_DISCOVERY = load_ssdp_fixture("ssdp_discovery.txt", DOMAIN)


@pytest.fixture
def mock_async_create_device():
    """Mock async_upnp_client create device."""
    with patch(
        "homeassistant.components.upnp.device.UpnpFactory.async_create_device"
    ) as mock_create:
        yield mock_create


@pytest.fixture(autouse=True)
def mock_igd_device(mock_async_create_device) -> IgdDevice:
    """Mock async_upnp_client device."""
    mock_upnp_device = create_autospec(UpnpDevice, instance=True)
    mock_upnp_device.device_url = TEST_DISCOVERY.ssdp_location
    mock_upnp_device.serial_number = TEST_DISCOVERY.upnp[ATTR_UPNP_SERIAL]

    mock_igd_device = create_autospec(IgdDevice)
    mock_igd_device.device_type = TEST_DISCOVERY.ssdp_st
    mock_igd_device.name = TEST_DISCOVERY.upnp[ATTR_UPNP_FRIENDLY_NAME]
    mock_igd_device.manufacturer = TEST_DISCOVERY.upnp[ATTR_UPNP_MANUFACTURER]
    mock_igd_device.model_name = TEST_DISCOVERY.upnp[ATTR_UPNP_MODEL_NAME]
    mock_igd_device.udn = TEST_DISCOVERY.ssdp_udn
    mock_igd_device.device = mock_upnp_device

    mock_igd_device.async_get_traffic_and_status_data.return_value = IgdState(
        timestamp=datetime.now(),
        bytes_received=0,
        bytes_sent=0,
        packets_received=0,
        packets_sent=0,
        connection_status="Connected",
        last_connection_error="",
        uptime=10,
        external_ip_address="8.9.10.11",
        kibibytes_per_sec_received=None,
        kibibytes_per_sec_sent=None,
        packets_per_sec_received=None,
        packets_per_sec_sent=None,
        port_mapping_number_of_entries=0,
    )

    mock_igd_device.async_subscribe_services = AsyncMock()

    mock_notify_server = create_autospec(AiohttpNotifyServer)
    mock_notify_server.event_handler = MagicMock()

    with (
        patch(
            "homeassistant.components.upnp.device.async_get_local_ip",
            return_value=(socket.AF_INET, "127.0.0.1"),
        ),
        patch(
            "homeassistant.components.upnp.device.IgdDevice.__new__",
            return_value=mock_igd_device,
        ),
        patch(
            "homeassistant.components.upnp.device.AiohttpNotifyServer.__new__",
            return_value=mock_notify_server,
        ),
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
def silent_ssdp_scanner() -> Generator[None]:
    """Start SSDP component and get Scanner, prevent actual SSDP traffic."""
    with (
        patch("homeassistant.components.ssdp.Scanner._async_start_ssdp_listeners"),
        patch("homeassistant.components.ssdp.Scanner._async_stop_ssdp_listeners"),
        patch("homeassistant.components.ssdp.Scanner.async_scan"),
        patch(
            "homeassistant.components.ssdp.Server._async_start_upnp_servers",
        ),
        patch(
            "homeassistant.components.ssdp.Server._async_stop_upnp_servers",
        ),
    ):
        yield


@pytest.fixture
async def ssdp_instant_discovery():
    """Instant discovery."""

    # Set up device discovery callback.
    async def register_callback(
        hass: HomeAssistant,
        callback: Callable[
            [SsdpServiceInfo, ssdp.SsdpChange], Coroutine[Any, Any, None] | None
        ],
        match_dict: dict[str, str] | None = None,
    ) -> MagicMock:
        """Immediately do callback."""
        await callback(TEST_DISCOVERY, ssdp.SsdpChange.ALIVE)
        return MagicMock()

    with (
        patch(
            "homeassistant.components.ssdp.async_register_callback",
            side_effect=register_callback,
        ) as mock_register,
        patch(
            "homeassistant.components.ssdp.async_get_discovery_info_by_st",
            return_value=[TEST_DISCOVERY],
        ) as mock_get_info,
    ):
        yield (mock_register, mock_get_info)


@pytest.fixture
async def ssdp_instant_discovery_multi_location():
    """Instant discovery."""

    test_discovery = copy.deepcopy(TEST_DISCOVERY)
    test_discovery.ssdp_location = TEST_LOCATION6  # "Default" location is IPv6.
    test_discovery.ssdp_all_locations = {TEST_LOCATION6, TEST_LOCATION}

    # Set up device discovery callback.
    async def register_callback(
        hass: HomeAssistant,
        callback: Callable[
            [SsdpServiceInfo, ssdp.SsdpChange], Coroutine[Any, Any, None] | None
        ],
        match_dict: dict[str, str] | None = None,
    ) -> MagicMock:
        """Immediately do callback."""
        await callback(test_discovery, ssdp.SsdpChange.ALIVE)
        return MagicMock()

    with (
        patch(
            "homeassistant.components.ssdp.async_register_callback",
            side_effect=register_callback,
        ) as mock_register,
        patch(
            "homeassistant.components.ssdp.async_get_discovery_info_by_st",
            return_value=[test_discovery],
        ) as mock_get_info,
    ):
        yield (mock_register, mock_get_info)


@pytest.fixture
async def ssdp_no_discovery():
    """No discovery."""

    # Set up device discovery callback.
    async def register_callback(
        hass: HomeAssistant,
        callback: Callable[
            [SsdpServiceInfo, ssdp.SsdpChange], Coroutine[Any, Any, None] | None
        ],
        match_dict: dict[str, str] | None = None,
    ) -> MagicMock:
        """Don't do callback."""
        return MagicMock()

    with (
        patch(
            "homeassistant.components.ssdp.async_register_callback",
            side_effect=register_callback,
        ) as mock_register,
        patch(
            "homeassistant.components.ssdp.async_get_discovery_info_by_st",
            return_value=[],
        ) as mock_get_info,
    ):
        yield (mock_register, mock_get_info)


@pytest.fixture
async def mock_config_entry(
    hass: HomeAssistant,
    ssdp_instant_discovery,
    mock_igd_device: IgdDevice,
    mock_mac_address_from_host,
) -> MockConfigEntry:
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

    # Store igd_device for binary_sensor/sensor tests.
    entry.igd_device = mock_igd_device

    # Load config_entry.
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
