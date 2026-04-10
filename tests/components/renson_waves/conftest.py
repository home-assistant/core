"""Fixtures for Renson WAVES tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.renson_waves.client import RensonWavesClient
from homeassistant.components.renson_waves.coordinator import (
    RensonWavesCoordinator,
    RensonWavesData,
)
from homeassistant.core import HomeAssistant

# Load constellation fixture
FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def mock_setup_entry(
    hass: HomeAssistant,
) -> AsyncMock:
    """Mock setup entry."""
    with open(FIXTURE_DIR / "constellation.json") as f:
        constellation_data = json.load(f)

    async def mock_async_setup_entry(hass, entry):
        """Mock setup entry."""
        return True

    return mock_async_setup_entry


@pytest.fixture
def mock_renson_client() -> AsyncMock:
    """Mock Renson WAVES client."""
    with open(FIXTURE_DIR / "constellation.json") as f:
        constellation_data = json.load(f)

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
    with open(FIXTURE_DIR / "constellation.json") as f:
        constellation_data = json.load(f)

    coordinator = RensonWavesCoordinator(hass, mock_renson_client)

    # Set up mock data
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
