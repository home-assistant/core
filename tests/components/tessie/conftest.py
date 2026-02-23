"""Fixtures for Tessie."""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch

import pytest

from .common import (
    COMMAND_OK,
    ENERGY_HISTORY,
    LIVE_STATUS,
    PRODUCTS,
    SCOPES,
    SITE_INFO,
    TEST_STATE_OF_ALL_VEHICLES,
    TEST_VEHICLE_BATTERY,
    TEST_VEHICLE_STATE_ONLINE,
    TEST_VEHICLE_STATUS_AWAKE,
)

# Tessie


@pytest.fixture(autouse=True)
def mock_get_state():
    """Mock get_state function."""
    with patch(
        "homeassistant.components.tessie.coordinator.get_state",
        return_value=TEST_VEHICLE_STATE_ONLINE,
    ) as mock_get_state:
        yield mock_get_state


@pytest.fixture(autouse=True)
def mock_get_status():
    """Mock get_status function."""
    with patch(
        "homeassistant.components.tessie.coordinator.get_status",
        return_value=TEST_VEHICLE_STATUS_AWAKE,
    ) as mock_get_status:
        yield mock_get_status


@pytest.fixture(autouse=True)
def mock_get_battery():
    """Mock get_battery function."""
    with (
        patch(
            "homeassistant.components.tessie.get_battery",
            return_value=TEST_VEHICLE_BATTERY,
        ) as mock_get_battery,
        patch(
            "homeassistant.components.tessie.coordinator.get_battery",
            new=mock_get_battery,
        ),
    ):
        yield mock_get_battery


@pytest.fixture(autouse=True)
def mock_get_state_of_all_vehicles():
    """Mock get_state_of_all_vehicles function."""
    with patch(
        "homeassistant.components.tessie.get_state_of_all_vehicles",
        return_value=TEST_STATE_OF_ALL_VEHICLES,
    ) as mock_get_state_of_all_vehicles:
        yield mock_get_state_of_all_vehicles


# Fleet API
@pytest.fixture(autouse=True)
def mock_scopes():
    """Mock scopes function."""
    with patch(
        "homeassistant.components.tessie.Tessie.scopes",
        return_value=SCOPES,
    ) as mock_scopes:
        yield mock_scopes


@pytest.fixture(autouse=True)
def mock_products():
    """Mock Tesla Fleet Api products method."""
    with patch(
        "homeassistant.components.tessie.Tessie.products", return_value=PRODUCTS
    ) as mock_products:
        yield mock_products


@pytest.fixture(autouse=True)
def mock_request():
    """Mock Tesla Fleet API request method."""
    with patch(
        "homeassistant.components.tessie.Tessie._request",
        return_value=COMMAND_OK,
    ) as mock_request:
        yield mock_request


@pytest.fixture(autouse=True)
def mock_live_status():
    """Mock Tesla Fleet API EnergySpecific live_status method."""
    with patch(
        "tesla_fleet_api.tessie.EnergySite.live_status",
        side_effect=lambda: deepcopy(LIVE_STATUS),
    ) as mock_live_status:
        yield mock_live_status


@pytest.fixture(autouse=True)
def mock_site_info():
    """Mock Tesla Fleet API EnergySpecific site_info method."""
    with patch(
        "tesla_fleet_api.tessie.EnergySite.site_info",
        side_effect=lambda: deepcopy(SITE_INFO),
    ) as mock_live_status:
        yield mock_live_status


@pytest.fixture(autouse=True)
def mock_energy_history():
    """Mock Tesla Fleet API EnergySite energy_history method."""
    with patch(
        "tesla_fleet_api.tessie.EnergySite.energy_history",
        side_effect=lambda *a, **kw: deepcopy(ENERGY_HISTORY),
    ) as mock_energy_history:
        yield mock_energy_history
