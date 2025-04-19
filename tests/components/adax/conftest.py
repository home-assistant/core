"""Fixtures for Adax testing."""

from typing import Any
from unittest.mock import patch

import pytest
import json

from homeassistant.components.adax.const import DOMAIN
from tests.common import AsyncMock, MockConfigEntry, load_fixture

from . import LOCAL_CONFIG, CLOUD_CONFIG

CLOUD_DEVICE_DATA: dict[str, Any] = [
    {
        "id": "1",
        "homeId": "1",
        "name": "Room 1",
        "temperature": 15,
        "targetTemperature": 20,
        "heatingEnabled": True,
    }
]

LOCAL_DEVICE_DATA: dict[str, Any] = {
    "current_temperature": 15,
    "target_temperature": 20,
}


@pytest.fixture(params=["cloud", "local"])
def mock_config_entry(request: pytest.FixtureRequest) -> MockConfigEntry:
    """Mock a config entry."""
    f = load_fixture(f"get_config_{request.param}.json", DOMAIN)
    entry_data = json.loads(f)
    return MockConfigEntry(domain=DOMAIN, data=entry_data)


@pytest.fixture
def mock_adax_cloud():
    """Mock climate data."""
    with patch("homeassistant.components.adax.coordinator.Adax") as mock_adax:
        mock_adax_class = mock_adax.return_value

        mock_adax_class.get_rooms = AsyncMock()
        mock_adax_class.get_rooms.return_value = CLOUD_DEVICE_DATA

        mock_adax_class.update = AsyncMock()
        mock_adax_class.update.return_value = None
        yield mock_adax_class


@pytest.fixture
def mock_adax_local():
    """Mock climate data."""
    with patch("homeassistant.components.adax.coordinator.AdaxLocal") as mock_adax:
        mock_adax_class = mock_adax.return_value

        mock_adax_class.get_status = AsyncMock()
        mock_adax_class.get_status.return_value = LOCAL_DEVICE_DATA
        yield mock_adax_class
