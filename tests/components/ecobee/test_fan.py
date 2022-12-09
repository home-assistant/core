"""The test for the ecobee thermostat ventilator module."""
from unittest import mock

import pytest

from homeassistant.components.ecobee import fan as ecobee


@pytest.fixture
def ecobee_fixture():
    """Set up ecobee mock."""
    vals = {
        "name": "Ecobee",
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


@pytest.fixture(name="ventilator")
def ventilator_fixture(data):
    """Set up ecobee ventilator object."""
    return ecobee.EcobeeVentilator(data, 1)


async def test_name(ventilator):
    """Test name property."""
    assert ventilator.name == "Ecobee Ventilator"


async def test_attribute(ventilator):
    """Test attribute and extra attribute of ventilator."""
    assert ventilator.state == "off"
    assert ventilator.extra_state_attributes == {
        "ventilator type": "hrv",
        "ventilator_min_on_time_home": 20,
        "ventilator_min_on_time_away": 10,
        "is_ventilator_timer_on": False,
    }


async def test_state_on_based_on_equipement_status(ecobee_fixture, ventilator):
    """Test the interpretation of on/off status based on the equipementStatus."""
    ecobee_fixture["equipmentStatus"] = "fan,ventilator"
    assert ventilator.state == "on"


async def test_set_ventilator_min_on_time_home(ventilator, data):
    """Test set ventilator min time home."""
    data.reset_mock()
    ventilator.set_ventilator_min_on_time_home(40)
    data.ecobee.set_ventilator_min_on_time_home.assert_has_calls([mock.call(1, 40)])


async def test_set_ventilator_min_on_time_away(ventilator, data):
    """Test set ventilator min time away."""
    data.reset_mock()
    ventilator.set_ventilator_min_on_time_away(30)
    data.ecobee.set_ventilator_min_on_time_away.assert_has_calls([mock.call(1, 30)])


async def test_set_ventilator_timer_on(ventilator, data):
    """Test set ventilator mode to on."""
    data.reset_mock()
    ventilator.set_ventilator_timer(True)
    data.ecobee.set_ventilator_timer.assert_has_calls([mock.call(1, True)])
