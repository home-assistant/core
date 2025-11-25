"""Integration tests for Overkiz hybrid mode (local + cloud device filtering)."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

from pyoverkiz.enums import Protocol, UIClass, UIWidget

from homeassistant.components.overkiz.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .test_config_flow import (
    TEST_EMAIL,
    TEST_GATEWAY_ID,
    TEST_HOST,
    TEST_PASSWORD,
    TEST_SERVER,
    TEST_TOKEN,
)

from tests.common import MockConfigEntry


def _create_mock_device(device_url: str) -> Mock:
    """Create a mock Device with the given URL."""
    device = Mock()
    device.device_url = device_url
    device.widget = UIWidget.POD
    device.ui_class = UIClass.POD
    device.protocol = Protocol.IO
    device.states = {}
    return device


def _create_mock_gateway(gateway_id: str) -> Mock:
    """Create a mock Gateway."""
    gateway = Mock()
    gateway.id = gateway_id
    gateway.type = Mock()
    gateway.type.beautify_name = "TaHoma Switch"
    gateway.sub_type = Mock()
    gateway.sub_type.beautify_name = "TaHoma Switch"
    gateway.connectivity = Mock()
    gateway.connectivity.protocol_version = "2023.4.4"
    return gateway


async def test_setup_cloud_entry_filters_devices_managed_by_local(
    hass: HomeAssistant,
) -> None:
    """Test cloud entry filters devices already managed by local entry during setup."""
    # 1. Create and load local entry with specific devices
    local_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{TEST_GATEWAY_ID}-local",
        version=2,
        data={
            "host": TEST_HOST,
            "token": TEST_TOKEN,
            "verify_ssl": True,
            "hub": TEST_SERVER,
            "api_type": "local",
        },
    )
    local_entry.add_to_hass(hass)

    # Create mock devices for local entry
    local_devices = [
        _create_mock_device("io://gateway/device_a"),
        _create_mock_device("io://gateway/device_b"),
        _create_mock_device("io://gateway/device_c"),
    ]

    # Create mock setup with local devices
    local_setup = Mock()
    local_setup.devices = local_devices
    local_setup.gateways = [_create_mock_gateway(TEST_GATEWAY_ID)]
    local_setup.root_place = None

    # Set up local entry
    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        login=AsyncMock(return_value=True),
        get_setup=AsyncMock(return_value=local_setup),
        get_scenarios=AsyncMock(return_value=[]),
        fetch_events=AsyncMock(return_value=[]),
    ):
        await hass.config_entries.async_setup(local_entry.entry_id)
        await hass.async_block_till_done()

    # Verify local entry is loaded
    assert local_entry.state is ConfigEntryState.LOADED

    # 2. Create cloud entry
    cloud_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{TEST_GATEWAY_ID}-cloud",
        version=2,
        data={
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "hub": TEST_SERVER,
            "api_type": "cloud",
        },
    )
    cloud_entry.add_to_hass(hass)

    # Create mock devices for cloud (includes A, B, C from local + D, E new)
    cloud_devices = [
        _create_mock_device("io://gateway/device_a"),  # In local - should filter
        _create_mock_device("io://gateway/device_b"),  # In local - should filter
        _create_mock_device("io://gateway/device_c"),  # In local - should filter
        _create_mock_device("io://gateway/device_d"),  # Cloud-only - should keep
        _create_mock_device("io://gateway/device_e"),  # Cloud-only - should keep
    ]

    cloud_setup = Mock()
    cloud_setup.devices = cloud_devices
    cloud_setup.gateways = [_create_mock_gateway(TEST_GATEWAY_ID)]
    cloud_setup.root_place = None

    # Set up cloud entry
    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        login=AsyncMock(return_value=True),
        get_setup=AsyncMock(return_value=cloud_setup),
        get_scenarios=AsyncMock(return_value=[]),
        fetch_events=AsyncMock(return_value=[]),
    ):
        await hass.config_entries.async_setup(cloud_entry.entry_id)
        await hass.async_block_till_done()

    # 3. Verify cloud entry only has devices D and E (A, B, C filtered)
    assert cloud_entry.state is ConfigEntryState.LOADED
    cloud_device_urls = set(cloud_entry.runtime_data.coordinator.devices.keys())

    # Should NOT contain local devices
    assert "io://gateway/device_a" not in cloud_device_urls
    assert "io://gateway/device_b" not in cloud_device_urls
    assert "io://gateway/device_c" not in cloud_device_urls

    # Should contain cloud-only devices
    assert "io://gateway/device_d" in cloud_device_urls
    assert "io://gateway/device_e" in cloud_device_urls
