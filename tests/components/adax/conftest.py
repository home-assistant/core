"""Fixtures for Adax testing."""

from typing import Any
from unittest.mock import patch

import pytest

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


@pytest.fixture
def mock_adax_cloud():
    """Mock climate data."""
    with patch("adax.Adax.get_rooms") as mock_adax_get_rooms:
        mock_adax_get_rooms.return_value = CLOUD_DEVICE_DATA
        yield mock_adax_get_rooms


@pytest.fixture
def mock_adax_local():
    """Mock climate data."""
    with patch("adax_local.Adax.get_status") as mock_adax_class_get_status:
        mock_adax_class_get_status.return_value = LOCAL_DEVICE_DATA
        yield mock_adax_class_get_status
