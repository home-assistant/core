"""Unit tests for Overkiz hybrid mode (local + cloud for same gateway)."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

from pyoverkiz.enums import APIType
import pytest

from homeassistant import config_entries
from homeassistant.components.overkiz import _get_entry_device_urls, async_migrate_entry
from homeassistant.components.overkiz.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .test_config_flow import (
    MOCK_GATEWAY_RESPONSE,
    TEST_EMAIL,
    TEST_GATEWAY_ID,
    TEST_HOST,
    TEST_PASSWORD,
    TEST_SERVER,
    TEST_TOKEN,
)

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_can_add_cloud_when_local_exists(hass: HomeAssistant) -> None:
    """Test that cloud entry can be added when local entry exists for same gateway."""
    # Setup existing local entry
    MockConfigEntry(
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
    ).add_to_hass(hass)

    # Start config flow for cloud
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "cloud"},
    )

    with (
        patch("pyoverkiz.client.OverkizClient.login", return_value=True),
        patch(
            "pyoverkiz.client.OverkizClient.get_gateways",
            return_value=MOCK_GATEWAY_RESPONSE,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )

    # Should succeed - cloud entry can coexist with local entry
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_EMAIL
    assert result["data"]["api_type"] == "cloud"


async def test_can_add_local_when_cloud_exists(hass: HomeAssistant) -> None:
    """Test that local entry can be added when cloud entry exists for same gateway."""
    # Setup existing cloud entry
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{TEST_GATEWAY_ID}-cloud",
        version=2,
        data={
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "hub": TEST_SERVER,
            "api_type": "cloud",
        },
    ).add_to_hass(hass)

    # Start config flow for local
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"hub": TEST_SERVER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_type": "local"},
    )

    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        login=AsyncMock(return_value=True),
        get_gateways=AsyncMock(return_value=MOCK_GATEWAY_RESPONSE),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": TEST_HOST,
                "token": TEST_TOKEN,
                "verify_ssl": True,
            },
        )

    # Should succeed - local entry can coexist with cloud entry
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_HOST
    assert result["data"]["api_type"] == "local"


async def test_discovery_aborts_when_local_exists(hass: HomeAssistant) -> None:
    """Test that discovery aborts when local entry exists."""
    MockConfigEntry(
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
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=DhcpServiceInfo(
            hostname="gateway-1234-5678-9123",
            ip="192.168.1.4",
            macaddress="f8811a000000",
        ),
        context={"source": config_entries.SOURCE_DHCP},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_discovery_aborts_when_cloud_exists(hass: HomeAssistant) -> None:
    """Test that discovery aborts when cloud entry exists."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{TEST_GATEWAY_ID}-cloud",
        version=2,
        data={
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "hub": TEST_SERVER,
            "api_type": "cloud",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=DhcpServiceInfo(
            hostname="gateway-1234-5678-9123",
            ip="192.168.1.4",
            macaddress="f8811a000000",
        ),
        context={"source": config_entries.SOURCE_DHCP},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_migration_v1_to_v2_cloud(hass: HomeAssistant) -> None:
    """Test migration of cloud config entry from v1 to v2."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,  # Old format (v1)
        version=1,
        data={
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "hub": TEST_SERVER,
            "api_type": "cloud",
        },
    )
    mock_entry.add_to_hass(hass)

    # Run migration
    result = await async_migrate_entry(hass, mock_entry)

    assert result is True
    assert mock_entry.version == 2
    assert mock_entry.unique_id == f"{TEST_GATEWAY_ID}-cloud"


async def test_migration_v1_to_v2_local(hass: HomeAssistant) -> None:
    """Test migration of local config entry from v1 to v2."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,  # Old format (v1)
        version=1,
        data={
            "host": TEST_HOST,
            "token": TEST_TOKEN,
            "verify_ssl": True,
            "hub": TEST_SERVER,
            "api_type": "local",
        },
    )
    mock_entry.add_to_hass(hass)

    # Run migration
    result = await async_migrate_entry(hass, mock_entry)

    assert result is True
    assert mock_entry.version == 2
    assert mock_entry.unique_id == f"{TEST_GATEWAY_ID}-local"


async def test_migration_v1_to_v2_defaults_to_cloud(hass: HomeAssistant) -> None:
    """Test migration defaults to cloud when api_type is not set."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,  # Old format (v1)
        version=1,
        data={
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "hub": TEST_SERVER,
            # No api_type - should default to cloud
        },
    )
    mock_entry.add_to_hass(hass)

    # Run migration
    result = await async_migrate_entry(hass, mock_entry)

    assert result is True
    assert mock_entry.version == 2
    assert mock_entry.unique_id == f"{TEST_GATEWAY_ID}-cloud"


async def test_cloud_filters_devices_managed_by_local(hass: HomeAssistant) -> None:
    """Test that cloud entry filters out devices already managed by local entry."""
    # Create a mock local entry that appears loaded with devices
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

    # Mock the entry state and runtime_data
    local_entry._async_set_state(hass, ConfigEntryState.LOADED, None)
    local_entry.runtime_data = Mock()
    local_entry.runtime_data.coordinator = Mock()
    local_entry.runtime_data.coordinator.devices = {
        "io://1234-5678-9012/device_a": Mock(),
        "io://1234-5678-9012/device_b": Mock(),
        "io://1234-5678-9012/device_c": Mock(),
    }

    # Get local device URLs (excluding a different entry)
    local_urls = _get_entry_device_urls(hass, "other_entry_id", APIType.LOCAL)

    # Should return the local entry's device URLs
    assert local_urls == {
        "io://1234-5678-9012/device_a",
        "io://1234-5678-9012/device_b",
        "io://1234-5678-9012/device_c",
    }


async def test_cloud_uses_device_when_local_doesnt_have_it(
    hass: HomeAssistant,
) -> None:
    """Test that cloud entry keeps devices not managed by local entry."""
    # Create a mock local entry with only some devices
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

    local_entry._async_set_state(hass, ConfigEntryState.LOADED, None)
    local_entry.runtime_data = Mock()
    local_entry.runtime_data.coordinator = Mock()
    local_entry.runtime_data.coordinator.devices = {
        "io://1234-5678-9012/device_a": Mock(),
        "io://1234-5678-9012/device_b": Mock(),
    }

    # Simulate cloud devices (some overlap, some don't)
    cloud_devices = [
        Mock(device_url="io://1234-5678-9012/device_a"),  # In local - should filter
        Mock(device_url="io://1234-5678-9012/device_b"),  # In local - should filter
        Mock(device_url="io://1234-5678-9012/device_c"),  # Not in local - should keep
        Mock(device_url="io://1234-5678-9012/device_d"),  # Not in local - should keep
    ]

    local_urls = _get_entry_device_urls(hass, "cloud_entry_id", APIType.LOCAL)

    # Filter cloud devices (same logic as in async_setup_entry)
    filtered_devices = [d for d in cloud_devices if d.device_url not in local_urls]

    # Should only have devices C and D
    assert len(filtered_devices) == 2
    assert filtered_devices[0].device_url == "io://1234-5678-9012/device_c"
    assert filtered_devices[1].device_url == "io://1234-5678-9012/device_d"


async def test_get_entry_device_urls_excludes_current_entry(
    hass: HomeAssistant,
) -> None:
    """Test that _get_entry_device_urls excludes the current entry."""
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

    local_entry._async_set_state(hass, ConfigEntryState.LOADED, None)
    local_entry.runtime_data = Mock()
    local_entry.runtime_data.coordinator = Mock()
    local_entry.runtime_data.coordinator.devices = {
        "io://1234-5678-9012/device_a": Mock(),
    }

    # When we pass the local entry's own ID, it should exclude itself
    local_urls = _get_entry_device_urls(hass, local_entry.entry_id, APIType.LOCAL)

    # Should return empty set since we're excluding the only local entry
    assert local_urls == set()
