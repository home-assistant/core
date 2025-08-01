"""Test fixtures for Autoskope integration."""

from unittest.mock import AsyncMock

from autoskope_client.models import Vehicle
import pytest

from homeassistant.components.autoskope.const import DEFAULT_HOST, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Autoskope",
        data={
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
            CONF_HOST: DEFAULT_HOST,
        },
        unique_id=f"test_user@{DEFAULT_HOST}",
    )


@pytest.fixture
def mock_vehicle_data():
    """Return mock vehicle data."""
    return {
        "id": "12345",
        "name": "Test Vehicle",
        "ex_pow": 12.5,
        "bat_pow": 3.7,
        "hdop": 1.2,
        "support_infos": {"imei": "123456789012345"},
        "model": "AutoskopeX",
    }


@pytest.fixture
def mock_position_data():
    """Return mock position data."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [8.6821267, 50.1109221],  # longitude, latitude
                },
                "properties": {
                    "carid": "12345",
                    "s": 0,  # speed
                    "dt": "2025-05-28T10:00:00Z",  # timestamp
                    "park": False,  # park mode
                },
            }
        ],
    }


@pytest.fixture
def mock_vehicle_with_position(mock_vehicle_data, mock_position_data):
    """Return a mock vehicle with position data."""
    vehicle_data = mock_vehicle_data.copy()
    return Vehicle.from_api(vehicle_data, mock_position_data)


@pytest.fixture
def mock_vehicles_list(mock_vehicle_with_position):
    """Return a list of mock vehicles."""
    return [mock_vehicle_with_position]


@pytest.fixture
def mock_autoskope_api():
    """Return a mock Autoskope API."""
    api = AsyncMock()
    api.authenticate.return_value = True
    return api
