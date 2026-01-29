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


async def test_cloud_waits_for_local_to_load(
    hass: HomeAssistant,
) -> None:
    """Test that cloud entry waits for local entry to load first."""
    # 1. Create local entry but don't load it yet
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

    cloud_devices = [
        _create_mock_device("io://gateway/device_a"),
        _create_mock_device("io://gateway/device_d"),
    ]

    cloud_setup = Mock()
    cloud_setup.devices = cloud_devices
    cloud_setup.gateways = [_create_mock_gateway(TEST_GATEWAY_ID)]
    cloud_setup.root_place = None

    # 3. Try to set up cloud - should raise ConfigEntryNotReady
    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        login=AsyncMock(return_value=True),
        get_setup=AsyncMock(return_value=cloud_setup),
        get_scenarios=AsyncMock(return_value=[]),
        fetch_events=AsyncMock(return_value=[]),
    ):
        await hass.config_entries.async_setup(cloud_entry.entry_id)
        await hass.async_block_till_done()

    # Cloud should be in SETUP_RETRY state (waiting for local)
    assert cloud_entry.state is ConfigEntryState.SETUP_RETRY


async def test_local_first_then_cloud_filters_devices(
    hass: HomeAssistant,
) -> None:
    """Test that when local loads first, cloud filters out local devices during setup."""
    # 1. Create and load local entry FIRST
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

    # Local manages devices A, B, C
    local_devices = [
        _create_mock_device("io://gateway/device_a"),
        _create_mock_device("io://gateway/device_b"),
        _create_mock_device("io://gateway/device_c"),
    ]

    local_setup = Mock()
    local_setup.devices = local_devices
    local_setup.gateways = [_create_mock_gateway(TEST_GATEWAY_ID)]
    local_setup.root_place = None

    # Set up local entry first
    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        login=AsyncMock(return_value=True),
        get_setup=AsyncMock(return_value=local_setup),
        get_scenarios=AsyncMock(return_value=[]),
        fetch_events=AsyncMock(return_value=[]),
    ):
        await hass.config_entries.async_setup(local_entry.entry_id)
        await hass.async_block_till_done()

    # Verify local entry is loaded with 3 devices
    assert local_entry.state is ConfigEntryState.LOADED
    local_device_urls = set(local_entry.runtime_data.coordinator.devices.keys())
    assert len(local_device_urls) == 3

    # 2. Now create and load cloud entry (which will filter local devices)
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

    # Cloud has all devices (A, B, C, D, E)
    cloud_devices = [
        _create_mock_device("io://gateway/device_a"),
        _create_mock_device("io://gateway/device_b"),
        _create_mock_device("io://gateway/device_c"),
        _create_mock_device("io://gateway/device_d"),
        _create_mock_device("io://gateway/device_e"),
    ]

    cloud_setup = Mock()
    cloud_setup.devices = cloud_devices
    cloud_setup.gateways = [_create_mock_gateway(TEST_GATEWAY_ID)]
    cloud_setup.root_place = None

    # Set up cloud entry (filters local devices during setup)
    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        login=AsyncMock(return_value=True),
        get_setup=AsyncMock(return_value=cloud_setup),
        get_scenarios=AsyncMock(return_value=[]),
        fetch_events=AsyncMock(return_value=[]),
    ):
        await hass.config_entries.async_setup(cloud_entry.entry_id)
        await hass.async_block_till_done()

    # 3. Verify cloud entry only has devices D and E (A, B, C filtered out)
    assert cloud_entry.state is ConfigEntryState.LOADED
    cloud_device_urls = set(cloud_entry.runtime_data.coordinator.devices.keys())

    # Cloud should not have devices A, B, C (managed by local)
    assert "io://gateway/device_a" not in cloud_device_urls
    assert "io://gateway/device_b" not in cloud_device_urls
    assert "io://gateway/device_c" not in cloud_device_urls

    # Cloud should have devices D and E
    assert "io://gateway/device_d" in cloud_device_urls
    assert "io://gateway/device_e" in cloud_device_urls
