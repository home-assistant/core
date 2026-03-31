"""Common fixtures for the CentriConnect/MyPropane API tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.centriconnect.const import DOMAIN
from homeassistant.const import CONF_DEVICE_ID, CONF_PASSWORD, CONF_USERNAME

from .const import TEST_PASSWORD, TEST_TANK_ID, TEST_TANK_NAME, TEST_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_TANK_ID,
        data={
            CONF_DEVICE_ID: TEST_TANK_ID,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
        title=TEST_TANK_NAME,
    )


@pytest.fixture
def mock_centriconnect_client() -> Generator[AsyncMock]:
    """Mock an CentriConnect/MyPropane client."""
    with patch(
        "aiocentriconnect.api.API.async_request",
        return_value={
            "AlertStatus": "No Alert",
            "Altitude": 123.456,
            "BatteryVolts": 4.19,
            "DeviceID": TEST_TANK_ID,
            "DeviceName": TEST_TANK_NAME,
            "DeviceTempCelsius": 17.0,
            "DeviceTempFahrenheit": 63.0,
            "LastPostTimeIso": "2026-02-27 22:00:31.000",
            "Latitude": 40.7128,
            "Longitude": -74.0060,
            "NextPostTimeIso": "2026-02-28 10:00:00.000",
            "SignalQualLTE": -107.0,
            "SolarVolts": 2.46,
            "TankLevel": 75.0,
            "TankSize": 1000,
            "TankSizeUnit": "Gallons",
            "VersionHW": "4.1",
            "VersionLTE": "1.1.2",
        },
    ) as mock_client:
        yield mock_client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.centriconnect.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
