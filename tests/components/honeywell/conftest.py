"""Fixtures for honeywell tests."""

from unittest.mock import AsyncMock, create_autospec, patch

import aiosomecomfort
import pytest

from homeassistant.components.honeywell.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def config_data():
    """Provide configuration data for tests."""
    return {CONF_USERNAME: "fake", CONF_PASSWORD: "user"}


@pytest.fixture
def config_entry(config_data):
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
        options={},
    )


@pytest.fixture
def device():
    """Mock a somecomfort.Device."""
    mock_device = create_autospec(aiosomecomfort.device.Device, instance=True)
    mock_device.deviceid = 1234567
    mock_device._data = {
        "canControlHumidification": False,
        "hasFan": False,
    }
    mock_device.system_mode = "off"
    mock_device.name = "device1"
    mock_device.current_temperature = 20
    mock_device.mac_address = "macaddress1"
    mock_device.outdoor_temperature = None
    mock_device.outdoor_humidity = None
    return mock_device


@pytest.fixture
def device_with_outdoor_sensor():
    """Mock a somecomfort.Device."""
    mock_device = create_autospec(aiosomecomfort.device.Device, instance=True)
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
    mock_device = create_autospec(aiosomecomfort.device.Device, instance=True)
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
    mock_location = create_autospec(aiosomecomfort.location.Location, instance=True)
    mock_location.locationid.return_value = "location1"
    mock_location.devices_by_id = {device.deviceid: device}
    return mock_location


@pytest.fixture(autouse=True)
def client(location):
    """Mock a somecomfort.SomeComfort client."""
    client_mock = create_autospec(aiosomecomfort.AIOSomeComfort, instance=True)
    client_mock.locations_by_id = {location.locationid: location}
    client_mock.login = AsyncMock(return_value=True)
    client_mock.discover = AsyncMock()

    with patch(
        "homeassistant.components.honeywell.aiosomecomfort.AIOSomeComfort"
    ) as sc_class_mock:
        sc_class_mock.return_value = client_mock
        yield client_mock
