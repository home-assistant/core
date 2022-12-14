"""The test for the ecobee thermostat number module."""
from unittest import mock

import pytest

from homeassistant.components.ecobee import number as ecobee


@pytest.fixture
def ecobee_fixture():
    """Set up ecobee mock."""
    vals = {
        "name": "Ecobee",
        "identifier": "123123123",
        "modelNumber": "athenaSmart",
        "program": {
            "climates": [
                {"name": "Climate1", "climateRef": "c1"},
                {"name": "Climate2", "climateRef": "c2"},
            ],
            "currentClimateRef": "c1",
        },
        "runtime": {
            "connected": True,
            "actualTemperature": 300,
            "actualHumidity": 15,
            "desiredHeat": 400,
            "desiredCool": 200,
            "desiredFanMode": "on",
        },
        "settings": {
            "hvacMode": "auto",
            "heatStages": 1,
            "coolStages": 1,
            "fanMinOnTime": 10,
            "heatCoolMinDelta": 50,
            "holdAction": "nextTransition",
            "ventilatorType": "hrv",
            "ventilatorMinOnTimeHome": 20,
            "ventilatorMinOnTimeAway": 10,
            "isVentilatorTimerOn": False,
        },
        "equipmentStatus": "fan",
        "events": [
            {
                "name": "Event1",
                "running": True,
                "type": "hold",
                "holdClimateRef": "away",
                "endDate": "2017-01-01 10:00:00",
                "startDate": "2017-02-02 11:00:00",
            }
        ],
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


@pytest.fixture(name="number")
def home_number_fixture(data):
    """Set up ecobee number min time home object."""
    return ecobee.EcobeeVentilatorMinTime(
        data,
        1,
        "home",
        "ventilatorMinOnTimeHome",
        data.ecobee.set_ventilator_min_on_time_home,
    )


async def test_name(number):
    """Test name property."""
    assert number.name == "Ventilator min time home"


async def test_value(number):
    """Test value."""
    assert number.native_value == 20


async def test_set_ventilator_min_on_time(number, data):
    """Test set ventilator min time home."""
    data.reset_mock()
    number.set_native_value(40)
    data.ecobee.set_ventilator_min_on_time_home.assert_has_calls([mock.call(1, 40)])
