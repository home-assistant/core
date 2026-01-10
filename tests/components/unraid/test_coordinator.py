"""Coordinator tests for the Unraid integration."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

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
    assert isinstance(data, UnraidSystemData)
    # Data is now raw dicts
    assert data.info["system"]["uuid"] == "abc-123"
    assert data.metrics["cpu"]["percentTotal"] == 25.5


@pytest.mark.asyncio
async def test_storage_coordinator_fetch_success(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test storage coordinator successfully fetches data."""
    mock_api_client.query.return_value = {
        "array": {
            "state": "STARTED",
            "capacity": {
                "kilobytes": {"total": 1000000, "used": 500000, "free": 500000}
            },
            "parityCheckStatus": {"status": "idle"},
            "boot": {"id": "flash", "name": "Flash", "device": "sda"},
            "disks": [{"id": "disk1", "name": "Disk 1", "device": "sdb"}],
            "parities": [],
            "caches": [],
        },
        "shares": [{"id": "share1", "name": "appdata", "size": 100000, "used": 50000}],
    }

    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert data is not None
    assert isinstance(data, UnraidStorageData)
    assert data.array_state == "STARTED"
    assert data.capacity is not None
    assert data.capacity["kilobytes"]["total"] == 1000000


@pytest.mark.asyncio
async def test_system_coordinator_handles_connection_error(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test system coordinator raises UpdateFailed on connection error."""
    mock_api_client.query.side_effect = aiohttp.ClientError("Connection refused")

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
    mock_api_client.query.side_effect = aiohttp.ClientError("Connection refused")

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
    """Test system coordinator raises UpdateFailed on 401 error."""
    mock_api_client.query.side_effect = aiohttp.ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=401,
        message="Unauthorized",
    )

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert "Authentication failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_system_coordinator_handles_timeout(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test system coordinator raises UpdateFailed on timeout."""
    mock_api_client.query.side_effect = TimeoutError("Request timed out")

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert "timeout" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_system_coordinator_parses_docker_containers(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test system coordinator parses Docker container data."""
    mock_api_client.query.return_value = {
        "info": {
            "system": {},
            "cpu": {"packages": {}},
            "os": {},
            "versions": {"core": {}},
        },
        "metrics": {"cpu": {}, "memory": {}},
        "docker": {
            "containers": [
                {
                    "id": "abc123",
                    "names": ["/plex"],
                    "state": "running",
                    "image": "plexinc/pms",
                },
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
    assert data.containers[0]["name"] == "plex"  # Normalized name (stripped leading /)


@pytest.mark.asyncio
async def test_storage_coordinator_parses_disks(
    hass: HomeAssistant, mock_config_entry, mock_api_client
) -> None:
    """Test storage coordinator parses disk data."""
    mock_api_client.query.return_value = {
        "array": {
            "state": "STARTED",
            "capacity": {
                "kilobytes": {"total": 1000000, "used": 500000, "free": 500000}
            },
            "parityCheckStatus": None,
            "boot": None,
            "disks": [
                {
                    "id": "disk1",
                    "name": "Disk 1",
                    "fsSize": 1000000,
                    "fsUsed": 500000,
                    "temp": 35,
                },
                {
                    "id": "disk2",
                    "name": "Disk 2",
                    "fsSize": 2000000,
                    "fsUsed": 1000000,
                    "temp": 38,
                },
            ],
            "parities": [
                {"id": "parity1", "name": "Parity", "size": 4000000},
            ],
            "caches": [
                {"id": "cache1", "name": "Cache", "fsSize": 500000, "fsUsed": 250000},
            ],
        },
        "shares": [],
    }

    coordinator = UnraidStorageCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )
    data = await coordinator._async_update_data()

    assert len(data.disks) == 2
    assert data.disks[0]["name"] == "Disk 1"
    assert data.disks[0]["type"] == "DATA"  # Default type set by coordinator

    assert len(data.parities) == 1
    assert data.parities[0]["type"] == "PARITY"

    assert len(data.caches) == 1
    assert data.caches[0]["type"] == "CACHE"


@pytest.mark.asyncio
async def test_system_coordinator_logs_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test system coordinator logs when connection recovers."""
    # First call fails
    mock_api_client.query.side_effect = aiohttp.ClientError("Connection refused")

    coordinator = UnraidSystemCoordinator(
        hass, mock_config_entry, mock_api_client, "tower"
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    # Second call succeeds
    mock_api_client.query.side_effect = None
    mock_api_client.query.return_value = {
        "info": {
            "system": {},
            "cpu": {"packages": {}},
            "os": {},
            "versions": {"core": {}},
        },
        "metrics": {"cpu": {}, "memory": {}},
        "docker": {"containers": []},
        "vms": {"domain": []},
        "upsDevices": [],
        "notifications": {"overview": {"unread": {"total": 0}}},
    }

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
