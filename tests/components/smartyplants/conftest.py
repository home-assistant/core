"""Fixtures for SmartyPlants tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

ACCOUNT_ID = "acct-0001"

SENSOR_FIXTURE = {
    "id": "sensor-1",
    "identifier": "device-12345",
    "name": "Sensor-device-12345",
    "isOnline": True,
    "batteryPercentage": 87,
    "lastDataReceived": "2026-08-19T10:00:00.000Z",
    "plant": {
        "id": "plant-1",
        "name": "Monstera",
        "species": "Monstera deliciosa",
        "commonNames": ["Swiss cheese plant"],
        "environment": "Living Room",
        "imageUrl": "https://cdn.smartyplants.test/monstera.jpg",
    },
    "health": {
        "score": 82,
        "isHealthy": True,
        "needsAttentionCount": 0,
        "classifications": [],
    },
    "readings": {
        "temperature": {
            "value": 22.5,
            "unit": "°C",
            "status": "OK",
            "optimalRange": {"low": 18, "high": 26},
            "min": 0,
            "max": 50,
            "isCalculating": False,
        },
        "humidity": {
            "value": 55,
            "unit": "%",
            "status": "OK",
            "optimalRange": None,
            "min": 0,
            "max": 100,
            "isCalculating": False,
        },
        "moisture": {
            "value": 41,
            "unit": "%",
            "status": "OK",
            "optimalRange": None,
            "min": 0,
            "max": 100,
            "isCalculating": False,
        },
        "light": {
            "value": 1200,
            "unit": "lx",
            "status": "OK",
            "optimalRange": None,
            "min": 0,
            "max": 10000,
            "isCalculating": False,
        },
        "lightQuality": {
            "value": 78,
            "status": "OPTIMAL",
            "optimalRange": {"low": 40, "high": 100},
            "min": 0,
            "max": 100,
            "isCalculating": False,
        },
        "fertiliser": {
            "daysUntilFertilise": 21,
            "status": "OK",
            "isCalculating": False,
        },
        "battery": {"value": 87, "unit": "%", "status": "OK"},
        "updatedAt": "2026-08-19T10:00:00.000Z",
    },
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Avoid setting the integration up during config flow tests."""
    with patch(
        "homeassistant.components.smartyplants.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """Return a client whose sensor fetch succeeds."""
    with patch(
        "homeassistant.components.smartyplants.config_flow.SmartyPlantsClient",
        autospec=True,
    ) as mock:
        client = mock.return_value
        client.async_verify = AsyncMock(return_value=ACCOUNT_ID)
        client.async_get_sensors = AsyncMock(return_value=[SENSOR_FIXTURE])
        client.async_get_plants = AsyncMock(return_value=[])
        yield client


PLANT_WITHOUT_SENSOR = {
    "id": "plant-9",
    "name": "New Fern",
    "imageUrl": None,
    "species": "Nephrolepis exaltata",
    "commonNames": ["Boston fern"],
    "environment": "Bathroom",
    "sensor": None,
    "health": {
        "score": None,
        "isHealthy": True,
        "needsAttentionCount": 0,
        "classifications": [],
    },
    "readings": None,
    "alerts": [],
    "needsAttention": False,
}
