"""Fixtures for the Tank Utility integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.tank_utility.const import DOMAIN
from homeassistant.const import CONF_DEVICES, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

MOCK_DEVICE_ID = "device_1"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test_password"

DEVICE_DATA = {
    "name": "My Propane Tank",
    "address": "123 Main St",
    "capacity": 500,
    "fuelType": "propane",
    "orientation": "horizontal",
    "status": "ok",
    "lastReading": {
        "tank": 78.43,
        "time": 1600000000,
        "time_iso": "2020-09-13T12:00:00Z",
    },
}


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a Tank Utility config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=TEST_EMAIL,
        data={
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_DEVICES: [MOCK_DEVICE_ID],
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock async_setup_entry."""
    with patch(
        "homeassistant.components.tank_utility.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_get_token() -> Generator[MagicMock]:
    """Mock auth.get_token."""
    with patch(
        "tank_utility.auth.get_token",
        return_value="mock_token",
    ) as mock:
        yield mock


@pytest.fixture
def mock_get_devices() -> Generator[MagicMock]:
    """Mock device.get_devices."""
    with patch(
        "tank_utility.device.get_devices",
        return_value=[MOCK_DEVICE_ID],
    ) as mock:
        yield mock


@pytest.fixture
def mock_get_device_data() -> Generator[MagicMock]:
    """Mock device.get_device_data."""
    with patch(
        "tank_utility.device.get_device_data",
        return_value=dict(DEVICE_DATA),
    ) as mock:
        yield mock
