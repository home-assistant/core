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
    ups_devices: list[dict[str, Any]] | None = None,
    containers: list[dict[str, Any]] | None = None,
    vms: list[dict[str, Any]] | None = None,
    notifications_unread: int = 0,
) -> UnraidSystemData:
    """Create a UnraidSystemData instance for testing using raw dicts.

    Note: API returns: cpu { packages { temp, totalPower } } where packages is
    a dict like {'temp': [38, 40], 'totalPower': 1.63}.
    - temp: array of per-package temperatures
    - totalPower: single float for total CPU power
    """
    # Build packages dict matching API structure
    packages: dict[str, Any] = {}
    if cpu_temps is not None:
        packages["temp"] = cpu_temps
    if cpu_power is not None:
        packages["totalPower"] = cpu_power

    return UnraidSystemData(
        info={
            "cpu": {"packages": packages},
            "os": {"uptime": uptime.isoformat() if uptime else None},
        },
        metrics={
            "cpu": {"percentTotal": cpu_percent},
            "memory": {
                "total": memory_total,
                "used": memory_used,
                "percentTotal": memory_percent,
            },
        },
        ups_devices=ups_devices or [],
        containers=containers or [],
        vms=vms or [],
        notifications_unread=notifications_unread,
    )


def make_storage_data(
    array_state: str | None = None,
    capacity: dict[str, Any] | None = None,
    parity_status: dict[str, Any] | None = None,
    disks: list[dict[str, Any]] | None = None,
    parities: list[dict[str, Any]] | None = None,
    caches: list[dict[str, Any]] | None = None,
    shares: list[dict[str, Any]] | None = None,
    boot: dict[str, Any] | None = None,
) -> UnraidStorageData:
    """Create a UnraidStorageData instance for testing using raw dicts."""
    # Provide default capacity if not specified and array_state is set
    if capacity is None and array_state is not None:
        capacity = {"kilobytes": {"total": 1000, "used": 500, "free": 500}}
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
