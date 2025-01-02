"""Fixtures for Teslemetry."""

from __future__ import annotations

from collections.abc import Generator
from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest

from .const import (
    COMMAND_OK,
    ENERGY_HISTORY,
    LIVE_STATUS,
    METADATA,
    PRODUCTS,
    SITE_INFO,
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
def mock_vehicle_data() -> Generator[AsyncMock]:
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
def mock_vehicle() -> Generator[AsyncMock]:
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
        return_value=COMMAND_OK,
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


@pytest.fixture(autouse=True)
def mock_site_info():
    """Mock Teslemetry Energy Specific site_info method."""
    with patch(
        "homeassistant.components.teslemetry.EnergySpecific.site_info",
        side_effect=lambda: deepcopy(SITE_INFO),
    ) as mock_live_status:
        yield mock_live_status


@pytest.fixture(autouse=True)
def mock_energy_history():
    """Mock Teslemetry Energy Specific site_info method."""
    with patch(
        "homeassistant.components.teslemetry.EnergySpecific.energy_history",
        return_value=ENERGY_HISTORY,
    ) as mock_live_status:
        yield mock_live_status


@pytest.fixture(autouse=True)
def mock_listen():
    """Mock Teslemetry Stream listen method."""
    with patch(
        "homeassistant.components.teslemetry.TeslemetryStream.listen",
    ) as mock_listen:
        yield mock_listen
