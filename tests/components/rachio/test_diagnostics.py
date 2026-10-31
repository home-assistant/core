"""Tests for the Rachio diagnostics."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rachio.const import CONF_MANUAL_RUN_MINS, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant

from .conftest import BASE_STATION_ID, BASE_STATION_SERIAL

MOCK_CONTROLLER = {
    "id": "controller-id",
    "name": "Test Controller",
    "serialNumber": "serial-number",
    "macAddress": "00:9D:6B:00:00:01",
    "model": "GENERATION3",
    "status": "ONLINE",
    "on": True,
    "paused": False,
    "deleted": False,
    "rainSensorTripped": False,
    "timeZone": "America/Denver",
    "latitude": 39.7,
    "longitude": -104.9,
    "zones": [
        {
            "id": "zone-id",
            "name": "Test Zone",
            "zoneNumber": 1,
            "enabled": True,
            "imageUrl": "https://example.com/zone.jpg",
            "customSlope": {"name": "ZERO_THREE"},
        }
    ],
    "scheduleRules": [
        {
            "id": "schedule-id",
            "name": "Morning",
            "enabled": True,
            "summary": "Every day at 6:00 AM",
            "totalDuration": 900,
            "type": "FIXED",
        }
    ],
    "flexScheduleRules": [],
}

MOCK_VALVE = {
    "id": "valve-id",
    "name": "Front Yard",
    "baseStationId": BASE_STATION_ID,
    "detectFlow": True,
    "state": {
        "reportedState": {
            "connected": True,
            "batteryStatus": "GOOD",
            "defaultRuntimeSeconds": 600,
            "firmwareVersion": "1.2.3",
        }
    },
}

MOCK_SCHEDULE_EVENT = {
    "programId": "program-id",
    "programName": "Evening",
    "start": "2026-10-28T18:00:00Z",
    "totalRunDurationSeconds": 900,
    "skippable": True,
    "valveRunSummaries": [
        {
            "valveId": "valve-id",
            "valveName": "Front Yard",
            "durationSeconds": 900,
        }
    ],
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry with options."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "test-api-key",
            CONF_WEBHOOK_ID: "rachio-test-webhook-id",
        },
        options={CONF_MANUAL_RUN_MINS: 15},
        unique_id="test-user-id",
    )


@pytest.fixture
def mock_rachio(mock_rachio: MagicMock) -> MagicMock:
    """Return a mocked Rachio client with a controller and a hose timer."""
    mock_rachio.person.get.return_value = (
        {"status": 200},
        {"username": "testuser", "id": "test-user-id", "devices": [MOCK_CONTROLLER]},
    )
    mock_rachio.valve.list_base_stations.return_value = (
        {"status": 200},
        {
            "baseStations": [
                {
                    "id": BASE_STATION_ID,
                    "serialNumber": BASE_STATION_SERIAL,
                    "macAddress": "F0:03:8C:00:00:01",
                    "reportedState": {"connected": True, "firmwareVersion": "2.0.1"},
                }
            ]
        },
    )
    mock_rachio.valve.list_valves.return_value = (
        {"status": 200},
        {"valves": [MOCK_VALVE]},
    )
    mock_rachio.summary.get_valve_day_views.return_value = (
        {"status": 200},
        {"valveDayViews": [{"valveProgramRunSummaries": [MOCK_SCHEDULE_EVENT]}]},
    )
    return mock_rachio


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
        == snapshot
    )
