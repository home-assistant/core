"""Fixtures for Tessie."""

from __future__ import annotations

from collections.abc import Generator
from copy import deepcopy
import time
from unittest.mock import AsyncMock, patch

import jwt
import pytest

from homeassistant.components.tesla_fleet.const import DOMAIN, SCOPES

from .const import LIVE_STATUS, PRODUCTS, SITE_INFO, VEHICLE_DATA, VEHICLE_ONLINE

from tests.common import MockConfigEntry

UID = "abc-123"


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture(name="scopes")
def mock_scopes() -> list[str]:
    """Fixture to set the scopes present in the OAuth token."""
    return SCOPES


@pytest.fixture
def normal_config_entry(expires_at: int, scopes: list[str]) -> MockConfigEntry:
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
            "auth_implementation": DOMAIN,
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
        "homeassistant.components.tesla_fleet.VehicleSpecific.vehicle",
        return_value=VEHICLE_ONLINE,
    ) as mock_vehicle:
        yield mock_vehicle


@pytest.fixture(autouse=True)
def mock_vehicle_data() -> Generator[AsyncMock]:
    """Mock Tesla Fleet API Vehicle Specific vehicle_data method."""
    with patch(
        "homeassistant.components.tesla_fleet.VehicleSpecific.vehicle_data",
        return_value=VEHICLE_DATA,
    ) as mock_vehicle_data:
        yield mock_vehicle_data


@pytest.fixture(autouse=True)
def mock_wake_up() -> Generator[AsyncMock]:
    """Mock Tesla Fleet API Vehicle Specific wake_up method."""
    with patch(
        "homeassistant.components.tesla_fleet.VehicleSpecific.wake_up",
        return_value=VEHICLE_ONLINE,
    ) as mock_wake_up:
        yield mock_wake_up


@pytest.fixture(autouse=True)
def mock_live_status() -> Generator[AsyncMock]:
    """Mock Tesla Fleet API Energy Specific live_status method."""
    with patch(
        "homeassistant.components.tesla_fleet.EnergySpecific.live_status",
        side_effect=lambda: deepcopy(LIVE_STATUS),
    ) as mock_live_status:
        yield mock_live_status


@pytest.fixture(autouse=True)
def mock_site_info() -> Generator[AsyncMock]:
    """Mock Tesla Fleet API Energy Specific site_info method."""
    with patch(
        "homeassistant.components.tesla_fleet.EnergySpecific.site_info",
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
