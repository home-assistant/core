"""Test the Tesla base class."""
from unittest.mock import MagicMock, Mock

import pytest
from teslajsonpy.exceptions import IncompleteCredentials

from homeassistant.components.tesla.tesla_device import TeslaDevice


@pytest.fixture
def tesla_api_mock():
    """Create tesla_device mock for the API."""
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
    return tesla_api_mock


@pytest.fixture
def tesla_device_mock(tesla_api_mock):
    """Mock tesla_device instance."""
    coordinator = Mock(last_update_success=True)
    return TeslaDevice(tesla_api_mock, coordinator)


@pytest.fixture
def tesla_inherited_mock(tesla_api_mock):
    """Mock tesla_device instance to test decorator."""

    class testClass(TeslaDevice):
        """Test class with two functions."""

        def __init__(self, tesla_device, coordinator):
            """Initialise the Tesla device."""
            super().__init__(tesla_device, coordinator)

        @TeslaDevice.Decorators.check_for_reauth
        async def need_reauth(self):
            """Raise incomplete credentials."""
            raise IncompleteCredentials("TEST")

        @TeslaDevice.Decorators.check_for_reauth
        async def no_reauth(self):
            """Return True."""
            return True

    coordinator = Mock(last_update_success=True)
    return testClass(tesla_api_mock, coordinator)


def test_tesla_init(tesla_device_mock):
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


async def test_tesla_added_to_hass(tesla_device_mock):
    """Test added to hass."""
    tesla_device_mock.hass = MagicMock()
    await tesla_device_mock.async_added_to_hass()
    assert tesla_device_mock.config_entry_id is not None


async def test_tesla_refresh(tesla_device_mock):
    """Test refresh."""
    tesla_device_mock.hass = MagicMock()
    tesla_device_mock.entity_id = "asdf"
    tesla_device_mock.tesla_device.attrs = {"refreshed": True}

    tesla_device_mock.refresh()
    assert tesla_device_mock.tesla_device.refresh.is_called_once()
    assert tesla_device_mock.extra_state_attributes == {
        "refreshed": True,
        "battery_charging": True,
        "battery_level": 100,
    }


def test_tesla_inherited_init(tesla_inherited_mock):
    """Test inherited device init."""
    assert tesla_inherited_mock.tesla_device is not None
    assert tesla_inherited_mock.config_entry_id is None
    assert tesla_inherited_mock.name == "name"
    assert tesla_inherited_mock.unique_id == "uniq_id"
    assert tesla_inherited_mock.icon == "mdi:battery"
    assert tesla_inherited_mock.device_info == {
        "identifiers": {("tesla", 1)},
        "manufacturer": "Tesla",
        "model": "car_type",
        "name": "car_name",
        "sw_version": "car_version",
    }
    assert tesla_inherited_mock.extra_state_attributes == {
        "battery_charging": True,
        "battery_level": 100,
    }


async def test_tesla_inherited_reauth_raised(tesla_inherited_mock):
    """Test need for reauth results in reload."""
    tesla_device_mock.hass = MagicMock()
    assert await tesla_inherited_mock.need_reauth() is None
    assert tesla_device_mock.hass.config_entries.async_reload.called_once()


async def test_tesla_inherited_no_reauth_raised(tesla_inherited_mock):
    """Test no need for reauth returns value."""
    tesla_device_mock.hass = MagicMock()
    assert await tesla_inherited_mock.no_reauth() is True
    assert not tesla_device_mock.hass.config_entries.async_reload.called
