"""The test for the Ecobee thermostat module."""
from unittest import mock

import pytest

from homeassistant.components.ecobee import humidifier as ecobee


@pytest.fixture
def ecobee_fixture():
    """Set up ecobee mock."""
    vals = {
        "name": "ecobee",
        "runtime": {
            "desiredHumidity": 30,
        },
        "settings": {
            "hasHumidifier": True,
            "humidifierMode": "auto",
        },
    }
    mock_ecobee = mock.Mock()
    mock_ecobee.__getitem__ = mock.Mock(side_effect=vals.__getitem__)
    mock_ecobee.__setitem__ = mock.Mock(side_effect=vals.__setitem__)
    return mock_ecobee


@pytest.fixture(name="data")
def data_fixture(ecobee_fixture):
    """Set up data mock."""
    data = mock.Mock()
    data.ecobee.get_thermostat.return_value = ecobee_fixture
    return data


@pytest.fixture(name="thermostat")
def humidifier_fixture(data):
    """Set up ecobee thermostat object."""
    return ecobee.EcobeeHumidifier(data, 1)


async def test_name(thermostat):
    """Test name property."""
    assert thermostat.name == "ecobee"


async def test_target_humidity(ecobee_fixture, thermostat):
    """Test target humidity."""
    assert thermostat.target_humidity == 30
    ecobee_fixture["runtime"]["desiredHumidity"] = 50
    assert thermostat.target_humidity == 50


async def test_set_mode(thermostat, data):
    """Test set humidifier mode setter."""
    data.reset_mock()
    thermostat.set_mode("auto")
    data.ecobee.set_humidifier_mode.assert_has_calls([mock.call(1, "auto")])
    data.reset_mock()
    thermostat.set_mode("manual")
    data.ecobee.set_humidifier_mode.assert_has_calls([mock.call(1, "manual")])
    data.reset_mock()
    thermostat.set_mode("off")
    data.ecobee.set_humidifier_mode.assert_has_calls([mock.call(1, "off")])
