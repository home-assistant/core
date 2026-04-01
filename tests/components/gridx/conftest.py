"""Common fixtures for the GridX integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

USERNAME = "test@example.com"
PASSWORD = "test-password"
OEM = "eon-home"

MOCK_LIVE_DATA = {
    "photovoltaic": 1512,
    "consumption": 600,
    "grid": -59,
    "production": 1512,
    "selfConsumption": 1453,
    "selfConsumptionRate": 0.96,
    "selfSufficiencyRate": 1.0,
    "selfSupply": 600,
    "totalConsumption": 600,
    "directConsumptionHousehold": 600,
    "directConsumptionHeatPump": 0,
    "directConsumptionEV": 0,
    "directConsumptionHeater": 0,
    "directConsumptionRate": 0.397,
    "gridMeterReadingNegative": 14081760000,
    "gridMeterReadingPositive": 7393320000,
    "measuredAt": "2024-05-08T09:42:18Z",
    "battery": {
        "capacity": 10000,
        "nominalCapacity": 10000,
        "power": -853,
        "remainingCharge": 7700,
        "stateOfCharge": 0.77,
    },
}

MOCK_HIST_DATA = [
    {
        "total": {
            "photovoltaic": 8500,
            "consumption": 4200,
            "production": 8500,
            "feedIn": 4300,
            "supply": 0,
            "selfConsumption": 4200,
            "selfSupply": 4200,
            "totalConsumption": 4200,
            "directConsumptionHousehold": 4200,
            "selfConsumptionRate": 0.494,
            "selfSufficiencyRate": 1.0,
        }
    }
]


@pytest.fixture
def mock_gridx_connector() -> Generator[MagicMock]:
    """Mock GridboxConnector so tests never hit the real network."""
    connector = MagicMock()
    connector.retrieve_live_data = AsyncMock(return_value=[MOCK_LIVE_DATA])
    connector.retrieve_historical_data = AsyncMock(return_value=MOCK_HIST_DATA)
    connector.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.gridx.config_flow._validate_credentials",
        ),
        patch(
            "homeassistant.components.gridx.AsyncGridboxConnector.create",
            AsyncMock(return_value=connector),
        ),
    ):
        yield connector
