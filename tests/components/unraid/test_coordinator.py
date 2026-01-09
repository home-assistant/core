"""Coordinator tests for the Unraid integration."""

from __future__ import annotations

import builtins
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError, ClientResponseError
import pytest
from unraid_api.exceptions import UnraidAPIError

from homeassistant.components.unraid.const import DOMAIN
from homeassistant.components.unraid.coordinator import (
    UnraidStorageCoordinator,
    UnraidSystemCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


@pytest.fixture
def mock_api_client():
    """Create a mock API client."""
    client = MagicMock()
    client.query = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Provide a mock config entry for coordinator tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-uuid-1234",
        data={
            "host": "192.168.1.100",
            "port": 80,
            "username": "root",
            "password": "test",
        },
        title="Test Server",
    )


@pytest.mark.asyncio
async def test_system_coordinator_initialization(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test UnraidSystemCoordinator initializes with 30s interval."""
    coordinator = UnraidSystemCoordinator(
        hass=hass,
        config_entry=mock_config_entry,
        api_client=mock_api_client,
        server_name="tower",
    )

    assert coordinator.name == "tower System"
    assert coordinator.update_interval == timedelta(seconds=30)
    assert coordinator.api_client == mock_api_client


@pytest.mark.asyncio
async def test_storage_coordinator_initialization(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test UnraidStorageCoordinator initializes with 5min interval."""
    coordinator = UnraidStorageCoordinator(
        hass=hass,
        config_entry=mock_config_entry,
        api_client=mock_api_client,
        server_name="tower",
    )

    assert coordinator.name == "tower Storage"
    assert coordinator.update_interval == timedelta(seconds=300)
    assert coordinator.api_client == mock_api_client


@pytest.mark.asyncio
async def test_system_coordinator_fetch_success(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test system coordinator successfully fetches data."""
    mock_api_client.query.return_value = {
        "info": {
            "time": "2025-12-23T10:30:00Z",
            "system": {"uuid": "abc-123"},
            "cpu": {"brand": "AMD Ryzen", "packages": {"temp": [45.2]}},
            "os": {"hostname": "tower"},
            "versions": {"core": {"unraid": "7.2.0", "api": "4.29.2"}},
        },
        "metrics": {
            "cpu": {"percentTotal": 25.5},
            "memory": {"total": 17179869184, "used": 8589934592, "percentTotal": 50.0},
        },
        "docker": {"containers": []},
        "vms": {"domain": []},
        "upsDevices": [],
        "notifications": {"overview": {"unread": {"total": 0}}},
    }

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert data is not None
    # Now returns UnraidSystemData dataclass instead of dict
    assert data.info is not None
    assert data.metrics is not None
    assert data.info.system.uuid == "abc-123"
    assert data.metrics.cpu.percent_total == 25.5
    assert mock_api_client.query.call_count >= 1


@pytest.mark.asyncio
async def test_storage_coordinator_fetch_success(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test storage coordinator successfully fetches data."""
    # Storage coordinator now makes two queries: array data + shares data
    array_response = {
        "array": {
            "state": "STARTED",
            "capacity": {
                "kilobytes": {"total": 1000000, "used": 400000, "free": 600000}
            },
            "disks": [],
            "parities": [],
            "caches": [],
        },
    }
    shares_response = {"shares": []}
    mock_api_client.query.side_effect = [array_response, shares_response]

    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert data is not None
    # Now returns UnraidStorageData dataclass instead of dict
    assert data.array_state == "STARTED"
    assert data.capacity is not None
    assert data.capacity.kilobytes.total == 1000000
    assert mock_api_client.query.call_count == 2


@pytest.mark.asyncio
async def test_coordinator_network_error_handling(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test coordinator handles network errors with UpdateFailed."""

    mock_api_client.query.side_effect = ClientError("Connection refused")

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    with pytest.raises(UpdateFailed, match="Connection refused"):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_coordinator_authentication_error_handling(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test coordinator handles authentication errors with UpdateFailed."""

    mock_api_client.query.side_effect = ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=401,
        message="Unauthorized",
    )

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    with pytest.raises(UpdateFailed, match="Authentication failed"):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_coordinator_graphql_error_handling(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test coordinator handles GraphQL errors with UpdateFailed."""
    mock_api_client.query.side_effect = Exception("GraphQL errors: Field not found")

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    with pytest.raises(UpdateFailed, match="GraphQL errors"):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_coordinator_timeout_error_handling(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test coordinator handles timeout errors with UpdateFailed."""
    mock_api_client.query.side_effect = builtins.TimeoutError("Request timeout")

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    with pytest.raises(UpdateFailed, match="timeout"):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_system_coordinator_queries_all_endpoints(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test system coordinator queries all required endpoints."""
    mock_response = {
        "info": {"system": {"uuid": "abc-123"}},
        "metrics": {"cpu": {"percentTotal": 25.5}},
        "notifications": {"overview": {"unread": {"total": 0}}},
    }
    # Docker query returns empty containers
    mock_docker_response = {"docker": {"containers": []}}
    # VMs query returns empty domains
    mock_vms_response = {"vms": {"domain": []}}
    # UPS query returns empty list
    mock_ups_response = {"upsDevices": []}

    mock_api_client.query.side_effect = [
        mock_response,
        mock_docker_response,
        mock_vms_response,
        mock_ups_response,
    ]

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    await coordinator._async_update_data()

    # Verify query was called 4 times (main + Docker + VMs + UPS)
    assert mock_api_client.query.call_count == 4

    # Check first query includes key fields (system info, metrics)
    first_call_args = mock_api_client.query.call_args_list[0][0][0]
    assert "info" in first_call_args.lower()
    assert "metrics" in first_call_args.lower()

    # Check second query is for Docker
    second_call_args = mock_api_client.query.call_args_list[1][0][0]
    assert "docker" in second_call_args.lower()

    # Check third query is for VMs
    third_call_args = mock_api_client.query.call_args_list[2][0][0]
    assert "vms" in third_call_args.lower()

    # Check fourth query is for UPS
    fourth_call_args = mock_api_client.query.call_args_list[3][0][0]
    assert "upsdevices" in fourth_call_args.lower()


@pytest.mark.asyncio
async def test_storage_coordinator_queries_all_endpoints(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test storage coordinator queries all required endpoints."""
    # Now storage coordinator makes two queries:
    # 1. Array/disk data
    # 2. Shares data (optional, queried separately for resilience)
    array_response = {
        "array": {
            "state": "STARTED",
            "capacity": {
                "kilobytes": {"total": 1000000, "used": 400000, "free": 600000}
            },
            "disks": [],
        },
    }
    shares_response = {
        "shares": [],
    }
    mock_api_client.query.side_effect = [array_response, shares_response]

    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    await coordinator._async_update_data()

    # Verify both queries were called
    assert mock_api_client.query.call_count == 2

    # First call should be array/disk data
    first_call_args = mock_api_client.query.call_args_list[0][0][0]
    assert "array" in first_call_args.lower()

    # Second call should be shares data
    second_call_args = mock_api_client.query.call_args_list[1][0][0]
    assert "shares" in second_call_args.lower()


@pytest.mark.asyncio
async def test_coordinator_custom_interval(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test coordinators can use custom intervals."""
    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower", update_interval=60
    )

    assert coordinator.update_interval == timedelta(seconds=60)


@pytest.mark.asyncio
async def test_coordinator_data_refresh_cycle(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test coordinator handles multiple refresh cycles."""
    mock_api_client.query.return_value = {
        "info": {"system": {"uuid": "abc-123"}},
        "metrics": {"cpu": {"percentTotal": 25.5}},
        "docker": {"containers": []},
        "vms": {"domain": []},
        "upsDevices": [],
        "notifications": {"overview": {"unread": {"total": 0}}},
    }

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    # First refresh
    data1 = await coordinator._async_update_data()
    assert data1 is not None
    assert data1.metrics.cpu.percent_total == 25.5

    # Second refresh
    mock_api_client.query.return_value = {
        "info": {"system": {"uuid": "abc-123"}},
        "metrics": {"cpu": {"percentTotal": 35.5}},
        "docker": {"containers": []},
        "vms": {"domain": []},
        "upsDevices": [],
        "notifications": {"overview": {"unread": {"total": 0}}},
    }
    data2 = await coordinator._async_update_data()
    assert data2 is not None
    assert data2.metrics.cpu.percent_total == 35.5


# =============================================================================
# Storage Coordinator Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
async def test_storage_coordinator_network_error_handling(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test storage coordinator handles network errors with UpdateFailed."""

    mock_api_client.query.side_effect = ClientError("Connection refused")

    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    with pytest.raises(UpdateFailed, match="Connection error"):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_storage_coordinator_authentication_error_handling(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test storage coordinator handles authentication errors with UpdateFailed."""

    mock_api_client.query.side_effect = ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=403,
        message="Forbidden",
    )

    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    with pytest.raises(UpdateFailed, match="Authentication failed"):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_storage_coordinator_http_error_handling(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test storage coordinator handles HTTP errors with UpdateFailed."""

    mock_api_client.query.side_effect = ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=500,
        message="Internal Server Error",
    )

    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    with pytest.raises(UpdateFailed, match="HTTP error 500"):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_storage_coordinator_timeout_error_handling(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test storage coordinator handles timeout errors with UpdateFailed."""

    mock_api_client.query.side_effect = builtins.TimeoutError("Timeout")

    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    with pytest.raises(UpdateFailed, match="timeout"):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_storage_coordinator_unexpected_error_handling(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test storage coordinator handles unexpected errors with UpdateFailed."""
    mock_api_client.query.side_effect = ValueError("Unexpected error")

    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    with pytest.raises(UpdateFailed, match="Unexpected error"):
        await coordinator._async_update_data()


# =============================================================================
# System Coordinator HTTP Error Tests
# =============================================================================


@pytest.mark.asyncio
async def test_system_coordinator_http_error_handling(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test system coordinator handles non-auth HTTP errors."""

    mock_api_client.query.side_effect = ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=500,
        message="Server Error",
    )

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    with pytest.raises(UpdateFailed, match="HTTP error 500"):
        await coordinator._async_update_data()


# =============================================================================
# Connection Recovery Tests
# =============================================================================


@pytest.mark.asyncio
async def test_system_coordinator_connection_recovery(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test system coordinator logs connection recovery."""

    # First call fails
    mock_api_client.query.side_effect = ClientError("Connection refused")
    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    # Now simulate recovery
    mock_api_client.query.side_effect = None
    mock_api_client.query.return_value = {
        "info": {"system": {"uuid": "abc-123"}},
        "metrics": {"cpu": {"percentTotal": 25.5}},
        "docker": {"containers": []},
        "vms": {"domain": []},
        "upsDevices": [],
        "notifications": {"overview": {"unread": {"total": 0}}},
    }

    data = await coordinator._async_update_data()
    assert data is not None
    assert "Connection restored" in caplog.text


@pytest.mark.asyncio
async def test_storage_coordinator_connection_recovery(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test storage coordinator logs connection recovery."""

    # First call fails
    mock_api_client.query.side_effect = ClientError("Connection refused")
    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    # Now simulate recovery - two queries: array data + shares data
    array_response = {
        "array": {
            "state": "STARTED",
            "capacity": {"kilobytes": {"total": 1000, "used": 500, "free": 500}},
            "disks": [],
            "parities": [],
            "caches": [],
        },
    }
    shares_response = {"shares": []}
    mock_api_client.query.side_effect = [array_response, shares_response]

    data = await coordinator._async_update_data()
    assert data is not None
    assert "Connection restored" in caplog.text


# =============================================================================
# Parsing Tests
# =============================================================================


@pytest.mark.asyncio
async def test_system_coordinator_parses_docker_containers(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test system coordinator correctly parses Docker containers."""
    mock_api_client.query.return_value = {
        "info": {"system": {"uuid": "abc-123"}},
        "metrics": {"cpu": {"percentTotal": 25.5}},
        "docker": {
            "containers": [
                {
                    "id": "ct:1",
                    "names": ["/plex"],
                    "state": "RUNNING",
                    "image": "plexinc/pms-docker",
                    "ports": [
                        {"privatePort": 32400, "publicPort": 32400, "type": "tcp"}
                    ],
                }
            ]
        },
        "vms": {"domain": []},
        "upsDevices": [],
        "notifications": {"overview": {"unread": {"total": 0}}},
    }

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert len(data.containers) == 1
    assert data.containers[0].name == "plex"  # Should strip leading /
    assert data.containers[0].state == "RUNNING"


@pytest.mark.asyncio
async def test_system_coordinator_parses_vms(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test system coordinator correctly parses VMs."""
    mock_api_client.query.return_value = {
        "info": {"system": {"uuid": "abc-123"}},
        "metrics": {"cpu": {"percentTotal": 25.5}},
        "docker": {"containers": []},
        "vms": {
            "domain": [
                {"id": "vm:1", "name": "Ubuntu", "state": "RUNNING"},
                {"id": "vm:2", "name": "Windows", "state": "SHUTOFF"},
            ]
        },
        "upsDevices": [],
        "notifications": {"overview": {"unread": {"total": 0}}},
    }

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert len(data.vms) == 2
    assert data.vms[0].name == "Ubuntu"
    assert data.vms[1].state == "SHUTOFF"


@pytest.mark.asyncio
async def test_system_coordinator_parses_ups_devices(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test system coordinator correctly parses UPS devices."""
    mock_api_client.query.return_value = {
        "info": {"system": {"uuid": "abc-123"}},
        "metrics": {"cpu": {"percentTotal": 25.5}},
        "docker": {"containers": []},
        "vms": {"domain": []},
        "upsDevices": [
            {
                "id": "ups:1",
                "name": "APC UPS",
                "status": "Online",
                "battery": {"chargeLevel": 100, "estimatedRuntime": 1800},
                "power": {"loadPercentage": 25.5},
            }
        ],
        "notifications": {"overview": {"unread": {"total": 0}}},
    }

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert len(data.ups_devices) == 1
    assert data.ups_devices[0].name == "APC UPS"
    assert data.ups_devices[0].battery.charge_level == 100


@pytest.mark.asyncio
async def test_system_coordinator_handles_ups_query_failure(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test system coordinator handles UPS query failure gracefully.

    When no UPS is configured, Unraid returns a GraphQL error for upsDevices.
    The coordinator should continue working with empty UPS list.
    """

    # Main query succeeds
    main_response = {
        "info": {"system": {"uuid": "abc-123"}},
        "metrics": {"cpu": {"percentTotal": 25.5}},
        "notifications": {"overview": {"unread": {"total": 0}}},
    }

    # Docker query succeeds
    docker_response = {"docker": {"containers": []}}

    # VMs query succeeds
    vms_response = {"vms": {"domain": []}}

    # UPS query fails (no UPS configured)
    ups_error = UnraidAPIError(
        "GraphQL query failed: No UPS data returned from apcaccess"
    )

    mock_api_client.query.side_effect = [
        main_response,
        docker_response,
        vms_response,
        ups_error,
    ]

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    # System data should be parsed successfully
    assert data is not None
    assert data.info.system.uuid == "abc-123"
    assert data.metrics.cpu.percent_total == 25.5

    # UPS list should be empty (not failed)
    assert data.ups_devices == []

    # Debug log should indicate UPS not available
    assert "UPS data not available" in caplog.text


@pytest.mark.asyncio
async def test_system_coordinator_handles_vms_query_failure(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test system coordinator handles VMs query failure gracefully.

    When VMs are not enabled, Unraid returns a GraphQL error for vms.
    The coordinator should continue working with empty VMs list.
    """

    # Main query succeeds
    main_response = {
        "info": {"system": {"uuid": "abc-123"}},
        "metrics": {"cpu": {"percentTotal": 25.5}},
        "notifications": {"overview": {"unread": {"total": 0}}},
    }

    # Docker query succeeds
    docker_response = {"docker": {"containers": []}}

    # VMs query fails (VMs not enabled)
    vms_error = UnraidAPIError("GraphQL query failed: VMs are not available")

    # UPS query succeeds
    ups_response = {"upsDevices": []}

    mock_api_client.query.side_effect = [
        main_response,
        docker_response,
        vms_error,
        ups_response,
    ]

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    # System data should be parsed successfully
    assert data is not None
    assert data.info.system.uuid == "abc-123"
    assert data.metrics.cpu.percent_total == 25.5

    # VMs list should be empty (not failed)
    assert data.vms == []

    # Debug log should indicate VMs not available
    assert "VM data not available" in caplog.text


@pytest.mark.asyncio
async def test_system_coordinator_handles_docker_query_failure(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test system coordinator handles Docker query failure gracefully.

    When Docker is not enabled, Unraid returns a GraphQL error for docker.
    The coordinator should continue working with empty containers list.
    """

    # Main query succeeds
    main_response = {
        "info": {"system": {"uuid": "abc-123"}},
        "metrics": {"cpu": {"percentTotal": 25.5}},
        "notifications": {"overview": {"unread": {"total": 0}}},
    }

    # Docker query fails (Docker not enabled)
    docker_error = UnraidAPIError("GraphQL query failed: Docker is not available")

    # VMs query succeeds
    vms_response = {"vms": {"domain": []}}

    # UPS query succeeds
    ups_response = {"upsDevices": []}

    mock_api_client.query.side_effect = [
        main_response,
        docker_error,
        vms_response,
        ups_response,
    ]

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    # System data should be parsed successfully
    assert data is not None
    assert data.info.system.uuid == "abc-123"
    assert data.metrics.cpu.percent_total == 25.5

    # Containers list should be empty (not failed)
    assert data.containers == []

    # Debug log should indicate Docker not available
    assert "Docker data not available" in caplog.text


@pytest.mark.asyncio
async def test_system_coordinator_parses_notifications(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test system coordinator correctly parses notifications."""
    mock_api_client.query.return_value = {
        "info": {"system": {"uuid": "abc-123"}},
        "metrics": {"cpu": {"percentTotal": 25.5}},
        "docker": {"containers": []},
        "vms": {"domain": []},
        "upsDevices": [],
        "notifications": {"overview": {"unread": {"total": 5}}},
    }

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert data.notifications_unread == 5


@pytest.mark.asyncio
async def test_system_coordinator_handles_invalid_container(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test system coordinator skips invalid containers."""
    mock_api_client.query.return_value = {
        "info": {"system": {"uuid": "abc-123"}},
        "metrics": {"cpu": {"percentTotal": 25.5}},
        "docker": {
            "containers": [
                {"id": "ct:1", "names": ["/good"], "state": "RUNNING"},
                {"invalid": "data"},  # Missing required fields
            ]
        },
        "vms": {"domain": []},
        "upsDevices": [],
        "notifications": {"overview": {"unread": {"total": 0}}},
    }

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert len(data.containers) == 1
    assert "Failed to parse container" in caplog.text


@pytest.mark.asyncio
async def test_system_coordinator_handles_invalid_vm(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test system coordinator skips invalid VMs."""
    mock_api_client.query.return_value = {
        "info": {"system": {"uuid": "abc-123"}},
        "metrics": {"cpu": {"percentTotal": 25.5}},
        "docker": {"containers": []},
        "vms": {
            "domain": [
                {"id": "vm:1", "name": "Good", "state": "RUNNING"},
                {"invalid": "vm_data"},  # Missing required fields
            ]
        },
        "upsDevices": [],
        "notifications": {"overview": {"unread": {"total": 0}}},
    }

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert len(data.vms) == 1
    assert "Failed to parse VM" in caplog.text


@pytest.mark.asyncio
async def test_system_coordinator_handles_invalid_ups(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test system coordinator skips invalid UPS devices."""
    mock_api_client.query.return_value = {
        "info": {"system": {"uuid": "abc-123"}},
        "metrics": {"cpu": {"percentTotal": 25.5}},
        "docker": {"containers": []},
        "vms": {"domain": []},
        "upsDevices": [
            {"id": "ups:1", "name": "Good UPS", "status": "Online"},
            {"invalid": "ups_data"},  # Missing required fields
        ],
        "notifications": {"overview": {"unread": {"total": 0}}},
    }

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert len(data.ups_devices) == 1
    assert "Failed to parse UPS" in caplog.text


@pytest.mark.asyncio
async def test_storage_coordinator_parses_disks_with_type(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test storage coordinator sets default disk types."""
    mock_api_client.query.return_value = {
        "array": {
            "state": "STARTED",
            "capacity": {"kilobytes": {"total": 1000, "used": 500, "free": 500}},
            "disks": [
                {"id": "disk:1", "idx": 1, "name": "Disk 1"},  # No type
            ],
            "parities": [
                {"id": "parity:1", "idx": 0, "name": "Parity"},  # No type
            ],
            "caches": [
                {"id": "cache:1", "idx": 0, "name": "Cache"},  # No type
            ],
        },
        "shares": [],
    }

    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert data.disks[0].type == "DATA"
    assert data.parities[0].type == "PARITY"
    assert data.caches[0].type == "CACHE"


@pytest.mark.asyncio
async def test_storage_coordinator_parses_boot_device(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test storage coordinator parses boot device."""
    array_response = {
        "array": {
            "state": "STARTED",
            "capacity": {"kilobytes": {"total": 1000, "used": 500, "free": 500}},
            "boot": {
                "id": "boot:1",
                "name": "Flash",
                "device": "sde",
                "fsSize": 32000,
                "fsUsed": 8000,
                "fsFree": 24000,
            },
            "disks": [],
            "parities": [],
            "caches": [],
        },
    }
    shares_response = {"shares": []}
    mock_api_client.query.side_effect = [array_response, shares_response]

    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert data.boot is not None
    assert data.boot.name == "Flash"
    assert data.boot.type == "FLASH"  # Default type set


@pytest.mark.asyncio
async def test_storage_coordinator_parses_shares(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test storage coordinator parses shares."""
    array_response = {
        "array": {
            "state": "STARTED",
            "capacity": {"kilobytes": {"total": 1000, "used": 500, "free": 500}},
            "disks": [],
            "parities": [],
            "caches": [],
        },
    }
    shares_response = {
        "shares": [
            {
                "id": "share:1",
                "name": "appdata",
                "size": 100000,
                "used": 50000,
                "free": 50000,
            },
            {
                "id": "share:2",
                "name": "media",
                "size": 500000,
                "used": 400000,
                "free": 100000,
            },
        ],
    }
    mock_api_client.query.side_effect = [array_response, shares_response]

    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert len(data.shares) == 2
    assert data.shares[0].name == "appdata"
    assert data.shares[1].name == "media"


@pytest.mark.asyncio
async def test_storage_coordinator_handles_invalid_disk(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test storage coordinator skips invalid disks."""
    array_response = {
        "array": {
            "state": "STARTED",
            "capacity": {"kilobytes": {"total": 1000, "used": 500, "free": 500}},
            "disks": [
                {"id": "disk:1", "idx": 1, "name": "Good Disk"},
                {"invalid": "disk_data"},  # Missing required id field
            ],
            "parities": [],
            "caches": [],
        },
    }
    shares_response = {"shares": []}
    mock_api_client.query.side_effect = [array_response, shares_response]

    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert len(data.disks) == 1
    assert "Failed to parse disk" in caplog.text


@pytest.mark.asyncio
async def test_storage_coordinator_handles_invalid_share(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test storage coordinator skips invalid shares."""
    array_response = {
        "array": {
            "state": "STARTED",
            "capacity": {"kilobytes": {"total": 1000, "used": 500, "free": 500}},
            "disks": [],
            "parities": [],
            "caches": [],
        },
    }
    shares_response = {
        "shares": [
            {"id": "share:1", "name": "good"},
            {"invalid": "share_data"},  # Missing required fields
        ],
    }
    mock_api_client.query.side_effect = [array_response, shares_response]

    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert len(data.shares) == 1
    assert "Failed to parse share" in caplog.text


@pytest.mark.asyncio
async def test_storage_coordinator_handles_shares_query_failure(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test storage coordinator gracefully handles shares query failure.

    This tests the fix for GitHub issue #132 where a share with null ID
    causes the GraphQL query to fail with 'Cannot return null for
    non-nullable field Share.id'.

    The fix queries shares separately so array/disk data is still available
    even when shares fail.
    """

    array_response = {
        "array": {
            "state": "STARTED",
            "capacity": {"kilobytes": {"total": 1000, "used": 500, "free": 500}},
            "disks": [{"id": "disk:1", "idx": 1, "name": "Disk 1"}],
            "parities": [],
            "caches": [],
        },
    }

    # Simulate shares query failure (like null ID error)
    def side_effect_func(query: str) -> dict:
        if "shares" in query.lower():
            raise UnraidAPIError("Cannot return null for non-nullable field Share.id")
        return array_response

    mock_api_client.query.side_effect = side_effect_func

    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    # Array data should still be available
    assert data is not None
    assert data.array_state == "STARTED"
    assert len(data.disks) == 1
    # Shares should be empty due to query failure
    assert data.shares == []
    # Debug log should indicate shares query failed
    assert "Shares query failed" in caplog.text


@pytest.mark.asyncio
async def test_storage_coordinator_handles_none_boot(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test storage coordinator handles missing boot device."""
    array_response = {
        "array": {
            "state": "STARTED",
            "capacity": {"kilobytes": {"total": 1000, "used": 500, "free": 500}},
            "boot": None,
            "disks": [],
            "parities": [],
            "caches": [],
        },
    }
    shares_response = {"shares": []}
    mock_api_client.query.side_effect = [array_response, shares_response]

    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert data.boot is None


@pytest.mark.asyncio
async def test_storage_coordinator_handles_none_capacity(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test storage coordinator handles missing capacity."""
    array_response = {
        "array": {
            "state": "STARTED",
            "capacity": None,
            "disks": [],
            "parities": [],
            "caches": [],
        },
    }
    shares_response = {"shares": []}
    mock_api_client.query.side_effect = [array_response, shares_response]

    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert data.capacity is None


@pytest.mark.asyncio
async def test_system_coordinator_handles_none_ups_list(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test system coordinator handles None upsDevices list."""
    mock_api_client.query.return_value = {
        "info": {"system": {"uuid": "abc-123"}},
        "metrics": {"cpu": {"percentTotal": 25.5}},
        "docker": {"containers": []},
        "vms": {"domain": []},
        "upsDevices": None,  # Can be None instead of empty list
        "notifications": {"overview": {"unread": {"total": 0}}},
    }

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert data.ups_devices == []


@pytest.mark.asyncio
async def test_system_coordinator_handles_none_notifications(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test system coordinator handles missing notifications count."""
    mock_api_client.query.return_value = {
        "info": {"system": {"uuid": "abc-123"}},
        "metrics": {"cpu": {"percentTotal": 25.5}},
        "docker": {"containers": []},
        "vms": {"domain": []},
        "upsDevices": [],
        "notifications": {"overview": {"unread": {"total": None}}},
    }

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert data.notifications_unread == 0


@pytest.mark.asyncio
async def test_system_coordinator_handles_container_without_names(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test system coordinator handles container without names list."""
    mock_api_client.query.return_value = {
        "info": {"system": {"uuid": "abc-123"}},
        "metrics": {"cpu": {"percentTotal": 25.5}},
        "docker": {
            "containers": [
                {"id": "ct:1", "names": [], "state": "RUNNING"},  # Empty names list
            ]
        },
        "vms": {"domain": []},
        "upsDevices": [],
        "notifications": {"overview": {"unread": {"total": 0}}},
    }

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    # Container without name is skipped due to validation error
    assert len(data.containers) == 0
    assert "Failed to parse container" in caplog.text
