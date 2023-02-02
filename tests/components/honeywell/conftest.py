"""Fixtures for honeywell tests."""

from unittest.mock import AsyncMock, create_autospec, patch

import aiosomecomfort as AIOSomecomfort
import pytest

from homeassistant.components.honeywell.const import (
    CONF_COOL_AWAY_TEMPERATURE,
    CONF_HEAT_AWAY_TEMPERATURE,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def config_data():
    """Provide configuration data for tests."""
    return {
        CONF_USERNAME: "fake",
        CONF_PASSWORD: "user",
    }


@pytest.fixture
def config_options():
    """Provide configuratio options for test."""
    return {CONF_COOL_AWAY_TEMPERATURE: 12, CONF_HEAT_AWAY_TEMPERATURE: 22}


@pytest.fixture
def config_entry(config_data, config_options):
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
        options=config_options,
    )


@pytest.fixture
def device():
    """Mock a somecomfort.Device."""
    mock_device = create_autospec(AIOSomecomfort.device.Device, instance=True)
    mock_device.deviceid = 1234567
    mock_device._data = {
        "canControlHumidification": True,
        "hasFan": True,
    }
    mock_device.system_mode = "off"
    mock_device.name = "device1"
    mock_device.current_temperature = 20
    mock_device.mac_address = "macaddress1"
    mock_device.outdoor_temperature = None
    mock_device.outdoor_humidity = None
    mock_device.is_alive = True
    mock_device.fan_running = False
    mock_device.fan_mode = "auto"
    mock_device.setpoint_cool = 26
    mock_device.setpoint_heat = 18
    mock_device.hold_heat = False
    mock_device.hold_cool = False
    mock_device.current_humidity = 50
    mock_device.equipment_status = "off"
    mock_device.equipment_output_status = "off"
    mock_device.raw_ui_data = {
        "SwitchOffAllowed": True,
        "SwitchAutoAllowed": True,
        "SwitchCoolAllowed": True,
        "SwitchHeatAllowed": True,
        "SwitchEmergencyHeatAllowed": True,
        "HeatUpperSetptLimit": 35,
        "HeatLowerSetptLimit": 20,
        "CoolUpperSetptLimit": 20,
        "CoolLowerSetptLimit": 10,
        "HeatNextPeriod": 10,
        "CoolNextPeriod": 10,
    }
    mock_device.raw_fan_data = {
        "fanModeOnAllowed": True,
        "fanModeAutoAllowed": True,
        "fanModeCirculateAllowed": True,
    }
    mock_device.set_setpoint_cool = AsyncMock()
    mock_device.set_setpoint_heat = AsyncMock()
    mock_device.set_system_mode = AsyncMock()
    mock_device.set_fan_mode = AsyncMock()
    mock_device.set_hold_heat = AsyncMock()
    mock_device.set_hold_cool = AsyncMock()
    mock_device.refresh = AsyncMock()
    mock_device.heat_away_temp = 10
    mock_device.cool_away_temp = 20

    return mock_device


@pytest.fixture
def device_with_outdoor_sensor():
    """Mock a somecomfort.Device."""
    mock_device = create_autospec(AIOSomecomfort.device.Device, instance=True)
    mock_device.deviceid = 1234567
    mock_device._data = {
        "canControlHumidification": False,
        "hasFan": False,
    }
    mock_device.system_mode = "off"
    mock_device.name = "device1"
    mock_device.current_temperature = 20
    mock_device.mac_address = "macaddress1"
    mock_device.temperature_unit = "C"
    mock_device.outdoor_temperature = 5
    mock_device.outdoor_humidity = 25
    return mock_device


@pytest.fixture
def another_device():
    """Mock a somecomfort.Device."""
    mock_device = create_autospec(AIOSomecomfort.device.Device, instance=True)
    mock_device.deviceid = 7654321
    mock_device._data = {
        "canControlHumidification": False,
        "hasFan": False,
    }
    mock_device.system_mode = "off"
    mock_device.name = "device2"
    mock_device.current_temperature = 20
    mock_device.mac_address = "macaddress1"
    mock_device.outdoor_temperature = None
    mock_device.outdoor_humidity = None
    return mock_device


@pytest.fixture
def location(device):
    """Mock a somecomfort.Location."""
    mock_location = create_autospec(AIOSomecomfort.location.Location, instance=True)
    mock_location.locationid.return_value = "location1"
    mock_location.devices_by_id = {device.deviceid: device}
    return mock_location


@pytest.fixture(autouse=True)
def client(location):
    """Mock a somecomfort.SomeComfort client."""
    client_mock = create_autospec(AIOSomecomfort.AIOSomeComfort, instance=True)
    client_mock.locations_by_id = {location.locationid: location}
    client_mock.login = AsyncMock(return_value=True)
    client_mock.discover = AsyncMock()

    with patch(
        "homeassistant.components.honeywell.AIOSomecomfort.AIOSomeComfort"
    ) as sc_class_mock:
        sc_class_mock.return_value = client_mock
        yield client_mock
