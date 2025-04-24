"""Fixtures for Autoskope integration tests."""

import logging
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.autoskope.const import DEFAULT_HOST, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


# This fixture provides a mocked AutoskopeApi instance
@pytest.fixture
def mock_api():
    """Create a mock API instance."""
    api = AsyncMock(name="MockAutoskopeApi")
    api.authenticate.return_value = True
    api.get_vehicles.return_value = []
    return api


# This fixture provides a configured MockConfigEntry
@pytest.fixture
async def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry and add it to Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": DEFAULT_HOST,
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-pass",
        },
        unique_id="test-user",
    )
    entry.add_to_hass(hass)
    return entry


# Fixture to provide mock vehicle data (can be customized in tests)
@pytest.fixture
def mock_vehicles_data():
    """Create mock raw vehicle data from API."""
    return [
        {
            "id": "123",
            "name": "Test Vehicle 1",
            "hdop": "1.0",
            "ex_pow": "12.5",
            "bat_pow": "4.1",
            "support_infos": {"imei": "IMEI123"},
            "device_type_id": "1",
        }
    ]


# Fixture to provide mock position data (can be customized in tests)
@pytest.fixture
def mock_position_data():
    """Create mock raw position data from API."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [13.0484209, 54.3166084]},
                "properties": {
                    "carid": "123",
                    "s": "0",  # Speed
                    "park": 1,  # Park mode (1 = parked, 0 = moving)
                    "dt": "2025-03-26 15:20:40",
                },
            }
        ],
    }
