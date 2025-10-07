"""Common fixtures for the Growatt server tests."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.components.growatt_server.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_growatt_api():
    """Return a mocked Growatt API."""
    with (
        patch("growattServer.OpenApiV1") as mock_v1_api_class,
        patch("growattServer.GrowattApi") as mock_classic_api_class,
    ):
        # Mock V1 API
        mock_v1_api = Mock()
        mock_v1_api_class.return_value = mock_v1_api

        # Mock V1 API methods
        mock_v1_api.device_list.return_value = {
            "devices": [
                {
                    "device_sn": "MIN123456",
                    "type": 7,  # MIN device type
                }
            ]
        }
        mock_v1_api.min_detail.return_value = {
            "deviceSn": "MIN123456",
            "acChargeEnable": 1,  # AC charge enabled (integer format) - SWITCH PLATFORM
        }
        mock_v1_api.min_settings.return_value = {}
        mock_v1_api.min_energy.return_value = {}
        mock_v1_api.plant_energy_overview.return_value = {
            "today_energy": 12.5,
            "total_energy": 1250.0,
            "current_power": 2500,
        }
        mock_v1_api.min_write_parameter.return_value = None

        # Mock Classic API
        mock_classic_api = Mock()
        mock_classic_api_class.return_value = mock_classic_api

        # Mock classic API methods
        mock_classic_api.login.return_value = {"success": True, "user": {"id": 12345}}
        mock_classic_api.plant_list.return_value = {"data": [{"plantId": "12345"}]}
        mock_classic_api.device_list.return_value = [
            {"deviceSn": "MIN123456", "deviceType": "min"}
        ]
        mock_classic_api.plant_info.return_value = {
            "deviceList": [],
            "totalEnergy": 1250.0,
            "todayEnergy": 12.5,
            "invTodayPpv": 2500,
            "plantMoneyText": "123.45/USD",
        }

        yield mock_v1_api


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
