"""Fixtures for Renson WAVES tests."""

from __future__ import annotations

from collections.abc import Generator
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.renson_waves.client import RensonWavesClient
from homeassistant.components.renson_waves.coordinator import (
    RensonWavesCoordinator,
    RensonWavesData,
)
from homeassistant.core import HomeAssistant

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_constellation_fixture() -> dict[str, object]:
    """Load the constellation fixture."""
    return json.loads((FIXTURE_DIR / "constellation.json").read_text(encoding="utf-8"))


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.renson_waves.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_renson_client() -> AsyncMock:
    """Mock Renson WAVES client."""
    constellation_data = _load_constellation_fixture()

    client = AsyncMock(spec=RensonWavesClient)
    client.async_get_constellation.return_value = constellation_data
    client.async_get_wifi_status.return_value = {
        "global": {
            "ssid": {"value": "HomeNetwork"},
            "connection_status": {"value": "connected"},
        }
    }
    client.async_get_global_uptime.return_value = {
        "global": {"uptime": {"value": 86400}}
    }
    client.async_get_decision_room.return_value = {
        "global": {"decision": {"value": "no"}, "level": {"value": 0}}
    }
    client.async_get_decision_silent.return_value = {
        "global": {"decision": {"value": "no"}, "reduction": {"value": 0}}
    }
    client.async_get_decision_breeze.return_value = {
        "global": {"decision": {"value": "no"}, "temperature": {"value": 20.0}}
    }
    client.host = "192.168.1.100"
    client.port = 8000

    return client


@pytest.fixture
def mock_coordinator(
    hass: HomeAssistant,
    mock_renson_client: AsyncMock,
) -> RensonWavesCoordinator:
    """Mock coordinator."""
    constellation_data = _load_constellation_fixture()

    coordinator = RensonWavesCoordinator(hass, mock_renson_client)
    coordinator.data = RensonWavesData(
        constellation=constellation_data,
        wifi_status={
            "global": {
                "ssid": {"value": "HomeNetwork"},
                "connection_status": {"value": "connected"},
            }
        },
        uptime={"global": {"uptime": {"value": 86400}}},
        decision_room={"global": {"decision": {"value": "no"}, "level": {"value": 0}}},
        decision_silent={
            "global": {"decision": {"value": "no"}, "reduction": {"value": 0}}
        },
        decision_breeze={
            "global": {"decision": {"value": "no"}, "temperature": {"value": 20.0}}
        },
    )
    coordinator.last_update_success = True

    return coordinator
