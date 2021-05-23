"""Fixtures for honeywell tests."""

from unittest.mock import create_autospec, patch

import pytest
import somecomfort

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
    mock_device = create_autospec(somecomfort.Device, instance=True)
    mock_device.deviceid.return_value = "device1"
    mock_device._data = {
        "canControlHumidification": False,
        "hasFan": False,
    }
    mock_device.system_mode = "off"
    mock_device.name = "device1"
    mock_device.current_temperature = 20
    mock_device.mac_address = "macaddress1"
    return mock_device


@pytest.fixture
def location(device):
    """Mock a somecomfort.Location."""
    mock_location = create_autospec(somecomfort.Location, instance=True)
    mock_location.locationid.return_value = "location1"
    mock_location.devices_by_id = {device.deviceid: device}
    return mock_location


@pytest.fixture(autouse=True)
def client(location):
    """Mock a somecomfort.SomeComfort client."""
    client_mock = create_autospec(somecomfort.SomeComfort, instance=True)
    client_mock.locations_by_id = {location.locationid: location}

    with patch(
        "homeassistant.components.honeywell.somecomfort.SomeComfort"
    ) as sc_class_mock:
        sc_class_mock.return_value = client_mock
        yield client_mock
