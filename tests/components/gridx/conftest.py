"""Common fixtures for the GridX integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

USERNAME = "test@example.com"
PASSWORD = "test-password"

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


@pytest.fixture
def mock_gridx_connector() -> Generator[MagicMock]:
    """Mock GridboxConnector so tests never hit the real network."""
    connector = MagicMock()
    connector.retrieve_live_data = AsyncMock(return_value=[MOCK_LIVE_DATA])
    connector.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.gridx.config_flow._validate_credentials",
        ),
        patch(
            "homeassistant.components.gridx.async_create_connector",
            AsyncMock(return_value=connector),
        ),
    ):
        yield connector
