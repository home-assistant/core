"""Shared pytest fixtures for Unraid integration tests."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.unraid.const import DOMAIN
from homeassistant.components.unraid.coordinator import (
    UnraidStorageData,
    UnraidSystemData,
)
from homeassistant.components.unraid.models import (
    ArrayCapacity,
    ArrayDisk,
    CapacityKilobytes,
    CpuPackages,
    CpuUtilization,
    DockerContainer,
    InfoCpu,
    InfoOs,
    MemoryUtilization,
    Metrics,
    ParityCheck,
    Share,
    SystemInfo,
    UPSDevice,
    VmDomain,
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
    cpu_temps: list[float] | None = None,
    cpu_power: float | None = None,
    uptime: datetime | None = None,
    ups_devices: list[UPSDevice] | None = None,
    containers: list[DockerContainer] | None = None,
    vms: list[VmDomain] | None = None,
    notifications_unread: int = 0,
) -> UnraidSystemData:
    """Create a UnraidSystemData instance for testing."""
    return UnraidSystemData(
        info=SystemInfo(
            cpu=InfoCpu(
                packages=CpuPackages(temp=cpu_temps or [], total_power=cpu_power)
            ),
            os=InfoOs(uptime=uptime),
        ),
        metrics=Metrics(
            cpu=CpuUtilization(percent_total=cpu_percent),
            memory=MemoryUtilization(
                total=memory_total,
                used=memory_used,
                percent_total=memory_percent,
            ),
        ),
        ups_devices=ups_devices or [],
        containers=containers or [],
        vms=vms or [],
        notifications_unread=notifications_unread,
    )


def make_storage_data(
    array_state: str | None = None,
    capacity: ArrayCapacity | None = None,
    parity_status: ParityCheck | None = None,
    disks: list[ArrayDisk] | None = None,
    parities: list[ArrayDisk] | None = None,
    caches: list[ArrayDisk] | None = None,
    shares: list[Share] | None = None,
    boot: ArrayDisk | None = None,
) -> UnraidStorageData:
    """Create a UnraidStorageData instance for testing."""
    # Provide default capacity if not specified and array_state is set
    if capacity is None and array_state is not None:
        capacity = ArrayCapacity(
            kilobytes=CapacityKilobytes(total=1000, used=500, free=500)
        )
    return UnraidStorageData(
        array_state=array_state,
        capacity=capacity,
        parity_status=parity_status,
        disks=disks or [],
        parities=parities or [],
        caches=caches or [],
        shares=shares or [],
        boot=boot,
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
