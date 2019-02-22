"""The tests for the Google Wifi platform."""
import json
from unittest import mock

import pytest
import requests_mock
import growatt

import homeassistant.components.sensor.growatt as victim


@mock.patch("growatt.GrowattApi.login", return_value={"userId": "1"})
def test_login(_):
    """Test logging in."""
    client = growatt.GrowattApi()
    login_success = victim.login(client, "foo", "bar")
    assert login_success


def test_convert_multiplier():
    """Test converting multipliers."""
    assert (
        victim.GrowattPlant(None, None, "", "").convert_multiplier(
            "kg", {"g": 1, "kg": 1000}
        )
        == 1000
    )


def test_convert_multiplier_no_value():
    """Test converting multipliers with exception."""
    with pytest.raises(ValueError):
        victim.GrowattPlant(None, None, "", "").convert_multiplier(
            "kg", {"g": 1, "mg": 0.001}
        )


def test_convert_to_kwh():
    """Test converting to kWh."""
    assert (
        victim.GrowattPlantTotals(None, None, "", "")._convert_to_kwh(
            "5.42", "GWh"
        )
        == 5420000
    )


@mock.patch(
    "growatt.GrowattApi.plant_detail", return_value={"data": "some-data"}
)
def test_plant_list(_):
    """Test getting the list of plants."""
    sensor = victim.GrowattPlant(None, growatt.GrowattApi(), "foo", "bar")
    login_res = sensor._client.plant_detail("1")
    assert login_res == {"data": "some-data"}


dummy_plant_info = {
    "data": [
        {
            "plantMoneyText": "137.9 ",
            "plantName": "my plant",
            "plantId": "107658",
            "isHaveStorage": "false",
            "todayEnergy": "0.6 kWh",
            "totalEnergy": "114.9 kWh",
            "currentPower": "142 W",
        }
    ],
    "totalData": {
        "currentPowerSum": "142 W",
        "CO2Sum": "114.9 T",
        "isHaveStorage": "false",
        "eTotalMoneyText": "137.9 ",
        "todayEnergySum": "0.6 kWh",
        "totalEnergySum": "114.9 kWh",
    },
    "success": True,
}


@mock.patch("growatt.GrowattApi.login", return_value={"userId": "1"})
@mock.patch("growatt.GrowattApi.plant_list", return_value=dummy_plant_info)
def test_today_energy(_, __):
    """Test extracting todays energy from plant."""
    with requests_mock.mock() as m:
        m.get(
            "https://server.growatt.com/PlantListAPI.do?userId=1",
            text=json.dumps(dummy_plant_info),
        )

        sensor = victim.GrowattPlantToday(
            None, growatt.GrowattApi(), "foo", "bar"
        )
        sensor.update()
        assert sensor._state == 0.6


@mock.patch("growatt.GrowattApi.login", return_value={"userId": "1"})
@mock.patch("growatt.GrowattApi.plant_list", return_value=dummy_plant_info)
def test_total_energy(_, __):
    """Test extracting total energy from plant."""
    with requests_mock.mock() as m:
        m.get(
            "https://server.growatt.com/PlantListAPI.do?userId=1",
            text=json.dumps(dummy_plant_info),
        )

        sensor = victim.GrowattPlantTotal(
            None, growatt.GrowattApi(), "foo", "bar"
        )
        sensor.update()
        assert sensor._state == 114.9


@mock.patch("growatt.GrowattApi.login", return_value={"userId": "1"})
@mock.patch("growatt.GrowattApi.plant_list", return_value=dummy_plant_info)
def test_current_energy(_, __):
    """Test extracting current energy from plant."""
    with requests_mock.mock() as m:
        m.get(
            "https://server.growatt.com/PlantListAPI.do?userId=1",
            text=json.dumps(dummy_plant_info),
        )

        sensor = victim.GrowattPlantCurrent(
            None, growatt.GrowattApi(), "foo", "bar"
        )
        sensor.update()
        assert sensor._state == 142.0
