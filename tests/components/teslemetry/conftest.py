"""Fixtures for Tessie."""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch

import pytest

from .const import (
    LIVE_STATUS,
    METADATA,
    PRODUCTS,
    RESPONSE_OK,
    VEHICLE_DATA,
    WAKE_UP_ONLINE,
)


@pytest.fixture(autouse=True)
def mock_metadata():
    """Mock Tesla Fleet Api metadata method."""
    with patch(
        "homeassistant.components.teslemetry.Teslemetry.metadata", return_value=METADATA
    ) as mock_products:
        yield mock_products


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
def mock_vehicle():
    """Mock Tesla Fleet API Vehicle Specific vehicle method."""
    with patch(
        "homeassistant.components.teslemetry.VehicleSpecific.vehicle",
        return_value=WAKE_UP_ONLINE,
    ) as mock_vehicle:
        yield mock_vehicle


@pytest.fixture(autouse=True)
def mock_request():
    """Mock Tesla Fleet API Vehicle Specific class."""
    with patch(
        "homeassistant.components.teslemetry.Teslemetry._request",
        return_value=RESPONSE_OK,
    ) as mock_request:
        yield mock_request


@pytest.fixture(autouse=True)
def mock_live_status():
    """Mock Teslemetry Energy Specific live_status method."""
    with patch(
        "homeassistant.components.teslemetry.EnergySpecific.live_status",
        side_effect=lambda: deepcopy(LIVE_STATUS),
    ) as mock_live_status:
        yield mock_live_status
