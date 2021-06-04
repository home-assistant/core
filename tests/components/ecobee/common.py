"""Common methods used across tests for Ecobee."""
from unittest import mock

import pytest

""" Common pytest fixtures """


@pytest.fixture
def ecobee_fixture():
    """Set up ecobee mock."""
    vals = {
        "name": "Ecobee",
        "program": {
            "climates": [
                {"name": "Climate1", "climateRef": "c1"},
                {"name": "Climate2", "climateRef": "c2"},
            ],
            "currentClimateRef": "c1",
        },
        "runtime": {
            "actualTemperature": 300,
            "actualHumidity": 15,
            "desiredHeat": 400,
            "desiredCool": 200,
            "desiredFanMode": "on",
            "desiredHumidity": 45,
        },
        "settings": {
            "hvacMode": "auto",
            "heatStages": 1,
            "coolStages": 1,
            "fanMinOnTime": 10,
            "heatCoolMinDelta": 50,
            "holdAction": "nextTransition",
            "hasHumidifier": True,
            "humidifierMode": "off",
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
