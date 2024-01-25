"""Fixtures for Tessie."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from .const import PRODUCTS, RESPONSE_OK, VEHICLE_DATA, WAKE_UP_ONLINE


@pytest.fixture(autouse=True)
def mock_products():
    """Mock Tesla Fleet Api products method."""
    with patch(
        "tesla_fleet_api.teslafleetapi.TeslaFleetApi.products",
    ) as mock_products:
        mock_products.return_value = PRODUCTS
        yield mock_products


@pytest.fixture(autouse=True)
def mock_vehicle_data():
    """Mock Tesla Fleet API Vehicle Specific vehicle_data method."""
    with patch(
        "tesla_fleet_api.vehiclespecific.VehicleSpecific.vehicle_data",
    ) as mock_vehicle_data:
        mock_vehicle_data.return_value = VEHICLE_DATA
        yield mock_vehicle_data


@pytest.fixture(autouse=True)
def mock_wake_up():
    """Mock Tesla Fleet API Vehicle Specific wake_up method."""
    with patch(
        "tesla_fleet_api.vehiclespecific.VehicleSpecific.wake_up",
    ) as mock_wake_up:
        mock_wake_up.return_value = WAKE_UP_ONLINE
        yield mock_wake_up


@pytest.fixture(autouse=True)
def mock_request():
    """Mock Tesla Fleet API Vehicle Specific class."""
    with patch(
        "tesla_fleet_api.teslafleetapi.TeslaFleetApi._request",
    ) as mock_request:
        mock_request.return_value = RESPONSE_OK
        yield mock_request
