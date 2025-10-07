"""Common fixtures for the Growatt server tests."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.components.growatt_server.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_growatt_api():
    """Return a mocked Growatt API."""
    with patch("growattServer.OpenApiV1") as mock_api_class:
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        # Mock V1 API methods
        mock_api.device_list.return_value = {
            "devices": [
                {
                    "device_sn": "MIN123456",
                    "type": 7,  # MIN device type
                }
            ]
        }
        mock_api.min_detail.return_value = {
            "deviceSn": "MIN123456",
            "chargePowerCommand": 50,  # 50% charge power
            "wchargeSOCLowLimit": 10,  # 10% charge stop SOC
            "disChargePowerCommand": 80,  # 80% discharge power
            "wdisChargeSOCLowLimit": 20,  # 20% discharge stop SOC
        }
        mock_api.min_settings.return_value = {}
        mock_api.min_energy.return_value = {}
        mock_api.plant_energy_overview.return_value = {
            "today_energy": 12.5,
            "total_energy": 1250.0,
            "current_power": 2500,
        }
        mock_api.min_write_parameter.return_value = None
        yield mock_api


@pytest.fixture
def mock_config_entry():
    """Return a mocked config entry for V1 API."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_type": "api_token",
            "token": "test_token_123",
            "url": "https://openapi.growatt.com/",
            "user_id": "12345",
            "plant_id": "plant_123",
            "name": "Test Plant",
        },
        unique_id="12345",
    )


@pytest.fixture
def mock_get_device_list():
    """Mock the get_device_list function."""
    with patch(
        "homeassistant.components.growatt_server.get_device_list"
    ) as mock_get_devices:
        mock_get_devices.return_value = (
            [{"deviceSn": "MIN123456", "deviceType": "min"}],
            "12345",
        )
        yield mock_get_devices
