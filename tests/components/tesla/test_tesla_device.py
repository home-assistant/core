"""Test the Tesla base class."""
from unittest.mock import Mock

import pytest

from homeassistant.components.tesla.tesla_device import TeslaDevice


@pytest.fixture
def tesla_device_mock():
    """Mock tesla_device instance."""
    coordinator = Mock(last_update_success=True)
    tesla_api_mock = Mock(uniq_name="uniq_id")
    tesla_api_mock.name = "name"
    tesla_api_mock.unique_id = "uniq_id"
    tesla_api_mock.id.return_value = 1
    tesla_api_mock.car_name.return_value = "car_name"
    tesla_api_mock.car_type = "car_type"
    tesla_api_mock.car_version = "car_version"
    tesla_api_mock.type = "battery sensor"
    tesla_api_mock.device_type = None
    tesla_api_mock.has_battery.return_value = True
    tesla_api_mock.battery_level.return_value = 100
    tesla_api_mock.battery_charging.return_value = True
    tesla_api_mock.attrs = {}
    tesla_api_mock.refresh.return_value = True
    return TeslaDevice(tesla_api_mock, coordinator)


async def test_tesla_init(tesla_device_mock):
    """Test init."""
    assert tesla_device_mock.tesla_device is not None
    assert tesla_device_mock.config_entry_id is None
    assert tesla_device_mock.name == "name"
    assert tesla_device_mock.unique_id == "uniq_id"
    assert tesla_device_mock.icon == "mdi:battery"
    assert tesla_device_mock.device_info == {
        "identifiers": {("tesla", 1)},
        "manufacturer": "Tesla",
        "model": "car_type",
        "name": "car_name",
        "sw_version": "car_version",
    }
    assert tesla_device_mock.extra_state_attributes == {
        "battery_charging": True,
        "battery_level": 100,
    }
