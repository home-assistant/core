"""Unit tests for Overkiz hybrid mode (local + cloud for same gateway)."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.overkiz import (
    _find_hybrid_local_entry,
    _get_gateway_id_from_unique_id,
    _hybrid_filter_local_devices,
    async_migrate_entry,
)
from homeassistant.components.overkiz.const import DOMAIN
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


def test_hybrid_filter_local_devices_filters_managed_devices() -> None:
    """Test that _hybrid_filter_local_devices filters out devices managed by local entry."""
    # Create a mock local entry with devices
    local_entry = Mock()
    local_entry.runtime_data = Mock()
    local_entry.runtime_data.coordinator = Mock()
    local_entry.runtime_data.coordinator.devices = {
        "io://1234-5678-9012/device_a": Mock(),
        "io://1234-5678-9012/device_b": Mock(),
        "io://1234-5678-9012/device_c": Mock(),
    }

    # Simulate cloud devices (some overlap with local)
    cloud_devices = [
        Mock(device_url="io://1234-5678-9012/device_a"),  # In local - should filter
        Mock(device_url="io://1234-5678-9012/device_b"),  # In local - should filter
        Mock(device_url="io://1234-5678-9012/device_c"),  # In local - should filter
        Mock(device_url="io://1234-5678-9012/device_d"),  # Not in local - should keep
        Mock(device_url="io://1234-5678-9012/device_e"),  # Not in local - should keep
    ]

    # Filter devices
    filtered = _hybrid_filter_local_devices(local_entry, cloud_devices)

    # Should only have devices D and E
    assert len(filtered) == 2
    assert filtered[0].device_url == "io://1234-5678-9012/device_d"
    assert filtered[1].device_url == "io://1234-5678-9012/device_e"


def test_hybrid_filter_local_devices_returns_all_when_no_runtime_data() -> None:
    """Test that _hybrid_filter_local_devices returns all devices when local entry has no runtime_data."""
    # Local entry without runtime_data (not yet loaded)
    local_entry = Mock(spec=[])  # Empty spec means no attributes

    cloud_devices = [
        Mock(device_url="io://1234-5678-9012/device_a"),
        Mock(device_url="io://1234-5678-9012/device_b"),
    ]

    filtered = _hybrid_filter_local_devices(local_entry, cloud_devices)

    # Should return all devices since local entry has no runtime_data
    assert len(filtered) == 2


def test_get_gateway_id_from_unique_id() -> None:
    """Test extracting gateway ID from unique_id."""
    # Test with local suffix
    assert _get_gateway_id_from_unique_id("1234-5678-9012-local") == "1234-5678-9012"

    # Test with cloud suffix
    assert _get_gateway_id_from_unique_id("1234-5678-9012-cloud") == "1234-5678-9012"

    # Test with None
    assert _get_gateway_id_from_unique_id(None) is None

    # Test with empty string
    assert _get_gateway_id_from_unique_id("") is None


def test_hybrid_filter_local_devices_returns_all_when_empty_local_devices() -> None:
    """Test that _hybrid_filter_local_devices returns all devices when local has no devices."""
    # Local entry with runtime_data but empty devices dict
    local_entry = Mock()
    local_entry.runtime_data = Mock()
    local_entry.runtime_data.coordinator = Mock()
    local_entry.runtime_data.coordinator.devices = {}

    cloud_devices = [
        Mock(device_url="io://1234-5678-9012/device_a"),
        Mock(device_url="io://1234-5678-9012/device_b"),
    ]

    filtered = _hybrid_filter_local_devices(local_entry, cloud_devices)

    # Should return all devices since local entry has no devices
    assert len(filtered) == 2


async def test_find_hybrid_local_entry_skips_cloud_entries(
    hass: HomeAssistant,
) -> None:
    """Test that _find_hybrid_local_entry skips entries with cloud api_type."""
    # Create a cloud entry for the same gateway (should be skipped)
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

    # Create the entry we're searching from (another cloud entry)
    current_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{TEST_GATEWAY_ID}-cloud2",
        version=2,
        data={
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "hub": TEST_SERVER,
            "api_type": "cloud",
        },
    )
    current_entry.add_to_hass(hass)

    # Should return None since there's no local entry
    result = _find_hybrid_local_entry(hass, current_entry)
    assert result is None


async def test_find_hybrid_local_entry_skips_different_gateway(
    hass: HomeAssistant,
) -> None:
    """Test that _find_hybrid_local_entry skips entries for different gateways."""
    # Create a local entry for a DIFFERENT gateway
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="different-gateway-id-local",
        version=2,
        data={
            "host": TEST_HOST,
            "token": TEST_TOKEN,
            "verify_ssl": True,
            "hub": TEST_SERVER,
            "api_type": "local",
        },
    ).add_to_hass(hass)

    # Create a cloud entry for our gateway
    current_entry = MockConfigEntry(
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
    current_entry.add_to_hass(hass)

    # Should return None since the local entry is for a different gateway
    result = _find_hybrid_local_entry(hass, current_entry)
    assert result is None


async def test_reauth_flow_with_invalid_unique_id(hass: HomeAssistant) -> None:
    """Test that reauth flow raises ValueError when unique_id is invalid."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=None,  # Invalid - no unique_id
        version=2,
        data={
            "username": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "hub": TEST_SERVER,
            "api_type": "cloud",
        },
    )
    mock_entry.add_to_hass(hass)

    # Start reauth flow - should raise ValueError
    with pytest.raises(ValueError, match="Reauth flow requires a valid unique_id"):
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": mock_entry.entry_id,
                "unique_id": mock_entry.unique_id,
            },
            data=mock_entry.data,
        )
