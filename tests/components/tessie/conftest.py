"""Fixtures for Tessie."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from .common import TEST_STATE_OF_ALL_VEHICLES, TEST_VEHICLE_STATE_ONLINE


@pytest.fixture
def mock_get_state():
    """Mock get_state function."""
    with patch(
        "homeassistant.components.tessie.coordinator.get_state",
        return_value=TEST_VEHICLE_STATE_ONLINE,
    ) as mock_get_state:
        yield mock_get_state


@pytest.fixture
def mock_get_state_of_all_vehicles():
    """Mock get_state_of_all_vehicles function."""
    with patch(
        "homeassistant.components.tessie.config_flow.get_state_of_all_vehicles",
        return_value=TEST_STATE_OF_ALL_VEHICLES,
    ) as mock_get_state_of_all_vehicles:
        yield mock_get_state_of_all_vehicles
