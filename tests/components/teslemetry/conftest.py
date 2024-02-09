"""Fixtures for Tessie."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from .const import PRODUCTS, RESPONSE_OK, VEHICLE_DATA, WAKE_UP_ONLINE


@pytest.fixture(autouse=True)
def mock_products():
    """Mock Tesla Fleet Api products method."""
    with patch(
        "homeassistant.components.teslemetry.Teslemetry.products", return_value=PRODUCTS
    ) as mock_products:
        yield mock_products


@pytest.fixture(autouse=True)
def mock_vehicle_data():
    """Mock Tesla Fleet API Vehicle Specific vehicle_data method."""
    with patch(
        "homeassistant.components.teslemetry.VehicleSpecific.vehicle_data",
        return_value=VEHICLE_DATA,
    ) as mock_vehicle_data:
        yield mock_vehicle_data


@pytest.fixture(autouse=True)
def mock_wake_up():
    """Mock Tesla Fleet API Vehicle Specific wake_up method."""
    with patch(
        "homeassistant.components.teslemetry.VehicleSpecific.wake_up",
        return_value=WAKE_UP_ONLINE,
    ) as mock_wake_up:
        yield mock_wake_up


@pytest.fixture(autouse=True)
def mock_request():
    """Mock Tesla Fleet API Vehicle Specific class."""
    with patch(
        "homeassistant.components.teslemetry.Teslemetry._request",
        return_value=RESPONSE_OK,
    ) as mock_request:
        yield mock_request
