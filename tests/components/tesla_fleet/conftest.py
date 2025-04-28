"""Fixtures for Tesla Fleet."""

from __future__ import annotations

from collections.abc import Generator
from copy import deepcopy
import time
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from tesla_fleet_api.const import Scope

from homeassistant.components.tesla_fleet.const import DOMAIN, SCOPES

from .const import (
    COMMAND_OK,
    ENERGY_HISTORY,
    LIVE_STATUS,
    PRODUCTS,
    SITE_INFO,
    VEHICLE_DATA,
    VEHICLE_ONLINE,
)

from tests.common import MockConfigEntry

UID = "abc-123"


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


def create_config_entry(
    expires_at: int, scopes: list[Scope], implementation: str = DOMAIN
) -> MockConfigEntry:
    """Create Tesla Fleet entry in Home Assistant."""
    access_token = jwt.encode(
        {
            "sub": UID,
            "aud": [],
            "scp": scopes,
            "ou_code": "NA",
        },
        key="",
        algorithm="none",
    )

    return MockConfigEntry(
        domain=DOMAIN,
        title=UID,
        unique_id=UID,
        data={
            "auth_implementation": implementation,
            "token": {
                "status": 0,
                "userid": UID,
                "access_token": access_token,
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": ",".join(scopes),
            },
        },
    )


@pytest.fixture
def normal_config_entry(expires_at: int) -> MockConfigEntry:
    """Create Tesla Fleet entry in Home Assistant."""
    return create_config_entry(expires_at, SCOPES)


@pytest.fixture
def noscope_config_entry(expires_at: int) -> MockConfigEntry:
    """Create Tesla Fleet entry in Home Assistant without scopes."""
    return create_config_entry(expires_at, [Scope.OPENID, Scope.OFFLINE_ACCESS])


@pytest.fixture
def readonly_config_entry(expires_at: int) -> MockConfigEntry:
    """Create Tesla Fleet entry in Home Assistant without scopes."""
    return create_config_entry(
        expires_at,
        [
            Scope.OPENID,
            Scope.OFFLINE_ACCESS,
            Scope.VEHICLE_DEVICE_DATA,
            Scope.ENERGY_DEVICE_DATA,
        ],
    )


@pytest.fixture
def bad_config_entry(expires_at: int) -> MockConfigEntry:
    """Create Tesla Fleet entry in Home Assistant."""
    return create_config_entry(expires_at, SCOPES, "bad")


@pytest.fixture(autouse=True)
def mock_products() -> Generator[AsyncMock]:
    """Mock Tesla Fleet Api products method."""
    with patch(
        "homeassistant.components.tesla_fleet.TeslaFleetApi.products",
        return_value=PRODUCTS,
    ) as mock_products:
        yield mock_products


@pytest.fixture(autouse=True)
def mock_vehicle_state() -> Generator[AsyncMock]:
    """Mock Tesla Fleet API Vehicle Specific vehicle method."""
    with patch(
        "tesla_fleet_api.tesla.VehicleFleet.vehicle",
        return_value=VEHICLE_ONLINE,
    ) as mock_vehicle:
        yield mock_vehicle


@pytest.fixture(autouse=True)
def mock_vehicle_data() -> Generator[AsyncMock]:
    """Mock Tesla Fleet API Vehicle Specific vehicle_data method."""
    with patch(
        "tesla_fleet_api.tesla.VehicleFleet.vehicle_data",
        return_value=VEHICLE_DATA,
    ) as mock_vehicle_data:
        yield mock_vehicle_data


@pytest.fixture(autouse=True)
def mock_wake_up() -> Generator[AsyncMock]:
    """Mock Tesla Fleet API Vehicle Specific wake_up method."""
    with patch(
        "tesla_fleet_api.tesla.VehicleFleet.wake_up",
        return_value=VEHICLE_ONLINE,
    ) as mock_wake_up:
        yield mock_wake_up


@pytest.fixture(autouse=True)
def mock_live_status() -> Generator[AsyncMock]:
    """Mock Tesla Fleet API Energy Specific live_status method."""
    with patch(
        "tesla_fleet_api.tesla.EnergySite.live_status",
        side_effect=lambda: deepcopy(LIVE_STATUS),
    ) as mock_live_status:
        yield mock_live_status


@pytest.fixture(autouse=True)
def mock_site_info() -> Generator[AsyncMock]:
    """Mock Tesla Fleet API Energy Specific site_info method."""
    with patch(
        "tesla_fleet_api.tesla.EnergySite.site_info",
        side_effect=lambda: deepcopy(SITE_INFO),
    ) as mock_live_status:
        yield mock_live_status


@pytest.fixture
def mock_find_server() -> Generator[AsyncMock]:
    """Mock Tesla Fleet find server method."""
    with patch(
        "homeassistant.components.tesla_fleet.TeslaFleetApi.find_server",
    ) as mock_find_server:
        yield mock_find_server


@pytest.fixture
def mock_request():
    """Mock all Tesla Fleet API requests."""
    with patch(
        "homeassistant.components.tesla_fleet.TeslaFleetApi._request",
        return_value=COMMAND_OK,
    ) as mock_request:
        yield mock_request


@pytest.fixture(autouse=True)
def mock_energy_history():
    """Mock Teslemetry Energy Specific site_info method."""
    with patch(
        "tesla_fleet_api.tesla.EnergySite.energy_history",
        return_value=ENERGY_HISTORY,
    ) as mock_live_status:
        yield mock_live_status


@pytest.fixture(autouse=True)
def mock_signed_command() -> Generator[AsyncMock]:
    """Mock Tesla Fleet Api signed_command method."""
    with patch(
        "tesla_fleet_api.tesla.VehicleSigned.signed_command",
        return_value=COMMAND_OK,
    ) as mock_signed_command:
        yield mock_signed_command
