"""Shared pytest fixtures for Unraid integration tests."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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
    UPSDevice,
    VmDomain,
)

from homeassistant.components.unraid.const import DOMAIN
from homeassistant.components.unraid.coordinator import (
    UnraidStorageData,
    UnraidSystemData,
)

from tests.common import MockConfigEntry

# Fixtures directory path
FIXTURES = Path(__file__).parent / "fixtures"


def load_json(name: str) -> dict[str, Any]:
    """Load JSON fixture from fixtures directory."""
    return json.loads((FIXTURES / name).read_text())


def make_system_data(
    cpu_percent: float | None = None,
    memory_used: int | None = None,
    memory_total: int | None = None,
    memory_percent: float | None = None,
    uptime: datetime | None = None,
    ups_devices: list[UPSDevice] | None = None,
    containers: list[DockerContainer] | None = None,
    vms: list[VmDomain] | None = None,
    notifications_unread: int = 0,
) -> UnraidSystemData:
    """Create a UnraidSystemData instance for testing using Pydantic models."""
    return UnraidSystemData(
        metrics=SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_total=memory_total,
            memory_used=memory_used,
            uptime=uptime,
        ),
        containers=containers or [],
        vms=vms or [],
        ups_devices=ups_devices or [],
        notifications=NotificationOverview(
            unread=NotificationOverviewCounts(total=notifications_unread),
        ),
    )


def make_storage_data(
    array_state: str | None = None,
    capacity_total: int = 0,
    capacity_used: int = 0,
    capacity_free: int = 0,
    parity_status: str | None = None,
    parity_progress: float | None = None,
    disks: list[ArrayDisk] | None = None,
    parities: list[ArrayDisk] | None = None,
    caches: list[ArrayDisk] | None = None,
    shares: list[Share] | None = None,
    boot: ArrayDisk | None = None,
) -> UnraidStorageData:
    """Create a UnraidStorageData instance for testing using Pydantic models."""
    return UnraidStorageData(
        array=UnraidArray(
            state=array_state,
            capacity=ArrayCapacity(
                kilobytes=CapacityKilobytes(
                    total=capacity_total,
                    used=capacity_used,
                    free=capacity_free,
                )
            ),
            parityCheckStatus=ParityCheck(
                status=parity_status,
                progress=parity_progress,
            ),
            disks=disks or [],
            parities=parities or [],
            caches=caches or [],
            boot=boot,
        ),
        shares=shares or [],
    )


@pytest.fixture
def mock_api_client():
    """Provide a mocked Unraid API client."""
    client = MagicMock()
    client.query.return_value = {}
    return client


@pytest.fixture
def hass_simple():
    """Provide a minimal HomeAssistant mock without Frame helper requirement."""
    hass = MagicMock()
    hass.data = {}
    hass.loop = None
    hass.config_entries = MagicMock()

    # Mock the frame helper to avoid "Frame helper not set up" error
    with patch("homeassistant.helpers.frame._hass.hass", hass):
        yield hass


@pytest.fixture
def mock_api():
    """Provide a mock API client with async methods."""
    client = MagicMock()
    client.query = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_config_entry_simple() -> MockConfigEntry:
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
