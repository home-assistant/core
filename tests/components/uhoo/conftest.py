"""Global fixtures for uHoo integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.uhoo.const import DOMAIN
from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry


@pytest.fixture
def mock_device() -> MagicMock:
    """Mock a uHoo device."""
    device = MagicMock()
    device.humidity = 45.5
    device.temperature = 22.0
    device.co = 1.5
    device.co2 = 450.0
    device.pm25 = 12.3
    device.air_pressure = 1013.25
    device.tvoc = 150.0
    device.no2 = 20.0
    device.ozone = 30.0
    device.virus_index = 2.0
    device.mold_index = 1.5
    device.device_name = "Test Device"
    device.serial_number = "23f9239m92m3ffkkdkdd"
    device.user_settings = {"temp": "c"}
    return device


@pytest.fixture
def mock_device2() -> MagicMock:
    """Mock a uHoo device."""
    device = MagicMock()
    device.humidity = 50.0
    device.temperature = 21.0
    device.co = 1.0
    device.co2 = 400.0
    device.pm25 = 10.0
    device.air_pressure = 1010.0
    device.tvoc = 100.0
    device.no2 = 15.0
    device.ozone = 25.0
    device.virus_index = 1.0
    device.mold_index = 1.0
    device.device_name = "Test Device 2"
    device.serial_number = "13e2r2fi2ii2i3993822"
    device.user_settings = {"temp": "c"}
    return device


@pytest.fixture
def mock_uhoo_client(mock_device) -> Generator[AsyncMock]:
    """Mock uHoo client."""
    with (
        patch(
            "homeassistant.components.uhoo.config_flow.Client",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.uhoo.Client",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_latest_data.return_value = [
            {
                "serialNumber": "23f9239m92m3ffkkdkdd",
                "deviceName": "Test Device",
                "humidity": 45.5,
                "temperature": 22.0,
                "co": 0.0,
                "co2": 400.0,
                "pm25": 10.0,
                "airPressure": 1010.0,
                "tvoc": 100.0,
                "no2": 15.0,
                "ozone": 25.0,
                "virusIndex": 1.0,
                "moldIndex": 1.0,
                "userSettings": {"temp": "c"},
            }
        ]
        client.devices = {"23f9239m92m3ffkkdkdd": mock_device}
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry for uHoo integration."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="valid-api-key-12345",
        data={CONF_API_KEY: "valid-api-key-12345"},
        title="uHoo (12345)",
        entry_id="01J0BC4QM2YBRP6H5G933CETT7",
    )


@pytest.fixture
def mock_setup_entry():
    """Mock the setup entry."""
    with patch(
        "homeassistant.components.uhoo.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup
