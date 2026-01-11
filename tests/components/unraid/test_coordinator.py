"""Coordinator tests for the Unraid integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from unraid_api.exceptions import (
    UnraidAPIError,
    UnraidAuthenticationError,
    UnraidConnectionError,
)
from unraid_api.models import (
    ArrayCapacity,
    ArrayDisk,
    CapacityKilobytes,
    DockerContainer,
    NotificationOverview,
    NotificationOverviewCounts,
    ParityCheck,
    Share,
    SystemMetrics,
    UnraidArray,
)

from homeassistant.components.unraid.const import DOMAIN
from homeassistant.components.unraid.coordinator import (
    UnraidStorageCoordinator,
    UnraidStorageData,
    UnraidSystemCoordinator,
    UnraidSystemData,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


@pytest.fixture
def mock_api_client():
    """Create a mock API client with typed methods."""
    client = MagicMock()
    # Mock the typed methods that the coordinator now uses
    client.get_system_metrics = AsyncMock()
    client.get_notification_overview = AsyncMock()
    client.typed_get_containers = AsyncMock()
    client.typed_get_vms = AsyncMock()
    client.typed_get_ups_devices = AsyncMock()
    client.typed_get_array = AsyncMock()
    client.typed_get_shares = AsyncMock()
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


@pytest.mark.asyncio
async def test_storage_coordinator_initialization(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test UnraidStorageCoordinator initializes with 300s interval."""
    coordinator = UnraidStorageCoordinator(
        hass=hass,
        config_entry=mock_config_entry,
        api_client=mock_api_client,
        server_name="tower",
    )

    assert coordinator.name == "tower Storage"
    assert coordinator.update_interval == timedelta(seconds=300)


@pytest.mark.asyncio
async def test_system_coordinator_fetch_success(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test system coordinator successfully fetches data using typed methods."""
    # Set up mock return values for typed library methods
    mock_api_client.get_system_metrics.return_value = SystemMetrics(
        cpu_percent=25.5,
        memory_total=17179869184,
        memory_used=8589934592,
        memory_percent=50.0,
        uptime=datetime(2025, 12, 23, 10, 30, 0, tzinfo=UTC),
    )
    mock_api_client.get_notification_overview.return_value = NotificationOverview(
        unread=NotificationOverviewCounts(total=3),
    )
    mock_api_client.typed_get_containers.return_value = []
    mock_api_client.typed_get_vms.return_value = []
    mock_api_client.typed_get_ups_devices.return_value = []

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert data is not None
    assert isinstance(data, UnraidSystemData)
    # Data now uses Pydantic models
    assert data.metrics.cpu_percent == 25.5
    assert data.metrics.memory_percent == 50.0
    assert data.notifications.unread.total == 3


@pytest.mark.asyncio
async def test_storage_coordinator_fetch_success(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test storage coordinator successfully fetches data using typed methods."""
    mock_api_client.typed_get_array.return_value = UnraidArray(
        state="STARTED",
        capacity=ArrayCapacity(
            kilobytes=CapacityKilobytes(total=1000000, used=500000, free=500000)
        ),
        parityCheckStatus=ParityCheck(status="idle"),
        boot=ArrayDisk(id="flash", name="Flash"),
        disks=[ArrayDisk(id="disk1", name="Disk 1")],
        parities=[],
        caches=[],
    )
    mock_api_client.typed_get_shares.return_value = [
        Share(id="share1", name="appdata", used=50000, free=50000),
    ]

    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert data is not None
    assert isinstance(data, UnraidStorageData)
    assert data.array.state == "STARTED"
    assert data.array.capacity.kilobytes.total == 1000000
    assert len(data.shares) == 1


@pytest.mark.asyncio
async def test_system_coordinator_handles_connection_error(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test system coordinator raises UpdateFailed on connection error."""
    mock_api_client.get_system_metrics.side_effect = UnraidConnectionError(
        "Connection refused"
    )

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert "Connection error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_storage_coordinator_handles_connection_error(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test storage coordinator raises UpdateFailed on connection error."""
    mock_api_client.typed_get_array.side_effect = UnraidConnectionError(
        "Connection refused"
    )

    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert "Connection error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_system_coordinator_handles_auth_error(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test system coordinator raises UpdateFailed on auth error."""
    mock_api_client.get_system_metrics.side_effect = UnraidAuthenticationError(
        "Invalid credentials"
    )

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert "Authentication failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_system_coordinator_handles_api_error(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test system coordinator raises UpdateFailed on API error."""
    mock_api_client.get_system_metrics.side_effect = UnraidAPIError("API error")

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert "API error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_system_coordinator_parses_docker_containers(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test system coordinator parses Docker container data."""
    mock_api_client.get_system_metrics.return_value = SystemMetrics()
    mock_api_client.get_notification_overview.return_value = NotificationOverview()
    mock_api_client.typed_get_containers.return_value = [
        DockerContainer(id="abc123", name="plex", state="running", image="plexinc/pms"),
    ]
    mock_api_client.typed_get_vms.return_value = []
    mock_api_client.typed_get_ups_devices.return_value = []

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert len(data.containers) == 1
    assert data.containers[0].name == "plex"
    assert data.containers[0].state == "running"


@pytest.mark.asyncio
async def test_storage_coordinator_parses_disks(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test storage coordinator parses disk data."""
    mock_api_client.typed_get_array.return_value = UnraidArray(
        state="STARTED",
        capacity=ArrayCapacity(
            kilobytes=CapacityKilobytes(total=1000000, used=500000, free=500000)
        ),
        disks=[
            ArrayDisk(
                id="disk1", name="Disk 1", fsSize=1000000, fsUsed=500000, temp=35
            ),
            ArrayDisk(
                id="disk2", name="Disk 2", fsSize=2000000, fsUsed=1000000, temp=38
            ),
        ],
        parities=[
            ArrayDisk(id="parity1", name="Parity", size=4000000),
        ],
        caches=[
            ArrayDisk(id="cache1", name="Cache", fsSize=500000, fsUsed=250000),
        ],
    )
    mock_api_client.typed_get_shares.return_value = []

    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert len(data.array.disks) == 2
    assert data.array.disks[0].name == "Disk 1"
    assert data.array.disks[0].temp == 35

    assert len(data.array.parities) == 1
    assert data.array.parities[0].name == "Parity"

    assert len(data.array.caches) == 1
    assert data.array.caches[0].name == "Cache"


@pytest.mark.asyncio
async def test_system_coordinator_logs_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test system coordinator logs when connection recovers."""
    # First call fails
    mock_api_client.get_system_metrics.side_effect = UnraidConnectionError(
        "Connection refused"
    )

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    # Second call succeeds
    mock_api_client.get_system_metrics.side_effect = None
    mock_api_client.get_system_metrics.return_value = SystemMetrics()
    mock_api_client.get_notification_overview.return_value = NotificationOverview()
    mock_api_client.typed_get_containers.return_value = []
    mock_api_client.typed_get_vms.return_value = []
    mock_api_client.typed_get_ups_devices.return_value = []

    await coordinator._async_update_data()

    assert "Connection restored" in caplog.text


@pytest.mark.asyncio
async def test_system_coordinator_custom_interval(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test system coordinator accepts custom polling interval."""
    coordinator = UnraidSystemCoordinator(
        hass=hass,
        config_entry=mock_config_entry,
        api_client=mock_api_client,
        server_name="tower",
        update_interval=60,
    )

    assert coordinator.update_interval == timedelta(seconds=60)


@pytest.mark.asyncio
async def test_storage_coordinator_custom_interval(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test storage coordinator accepts custom polling interval."""
    coordinator = UnraidStorageCoordinator(
        hass=hass,
        config_entry=mock_config_entry,
        api_client=mock_api_client,
        server_name="tower",
        update_interval=600,
    )

    assert coordinator.update_interval == timedelta(seconds=600)


@pytest.mark.asyncio
async def test_system_coordinator_optional_services_fail_gracefully(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test optional services (Docker, VMs, UPS) fail gracefully."""
    mock_api_client.get_system_metrics.return_value = SystemMetrics(cpu_percent=50.0)
    mock_api_client.get_notification_overview.return_value = NotificationOverview()
    # Simulate Docker/VMs/UPS not enabled or failing
    mock_api_client.typed_get_containers.side_effect = UnraidAPIError("Docker disabled")
    mock_api_client.typed_get_vms.side_effect = UnraidAPIError("VMs disabled")
    mock_api_client.typed_get_ups_devices.side_effect = UnraidAPIError("No UPS found")

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    # Should succeed with empty lists for optional services
    assert data is not None
    assert data.metrics.cpu_percent == 50.0
    assert data.containers == []
    assert data.vms == []
    assert data.ups_devices == []
