"""The tests for the Growatt platform."""
from unittest import mock

import growatt
import pytest

import homeassistant.components.growatt.sensor as growatt_sensor


@mock.patch("growatt.GrowattApi.login", return_value={"userId": "1"})
def test_login(_):
    """Test logging in."""
    client = growatt.GrowattApi()
    login_success = growatt_sensor.login(client, "foo", "bar")
    assert login_success


def test_convert_multiplier():
    """Test converting multipliers."""
    assert (
        growatt_sensor.GrowattPlant.convert_multiplier(
            "kg", {"g": 1, "kg": 1000}
        )
        == 1000
    )


def test_convert_multiplier_no_value():
    """Test converting multipliers with exception."""
    with pytest.raises(ValueError):
        growatt_sensor.GrowattPlant.convert_multiplier(
            "kg", {"g": 1, "mg": 0.001}
        )


def test_convert_to_kwh():
    """Test converting to kWh."""
    assert (
        growatt_sensor.GrowattPlantTotals(
            None, "", "", "", ""
        )._convert_to_kwh("5.42", "GWh")
        == 5420000
    )


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
    "plantMoneyText": "137.9 ",
    "plantName": "my plant",
    "plantId": "107658",
    "isHaveStorage": "false",
    "todayEnergy": "0.6 kWh",
    "totalEnergy": "114.9 kWh",
    "currentPower": "142 W",
}


@mock.patch("growatt.GrowattApi.login", return_value={"userId": "1"})
@mock.patch("growatt.GrowattApi.plant_list", return_value=dummy_plant_info)
def test_today_energy(_, __):
    """Test extracting todays energy from plant."""
    sensor = growatt_sensor.GrowattPlantTotals(
        growatt.GrowattApi(), "foo", "bar", "today", "todayEnergySum"
    )
    sensor.update()
    assert sensor.state == 0.6


@mock.patch("growatt.GrowattApi.login", return_value={"userId": "1"})
@mock.patch("growatt.GrowattApi.plant_list", return_value=dummy_plant_info)
def test_total_energy(_, __):
    """Test extracting total energy from plant."""
    sensor = growatt_sensor.GrowattPlantTotals(
        growatt.GrowattApi(), "foo", "bar", "total", "totalEnergySum"
    )
    sensor.update()
    assert sensor.state == 114.9


@mock.patch("growatt.GrowattApi.login", return_value={"userId": "1"})
@mock.patch("growatt.GrowattApi.plant_list", return_value=dummy_plant_info)
def test_current_energy(_, __):
    """Test extracting current energy from plant."""
    sensor = growatt_sensor.GrowattPlantCurrent(
        growatt.GrowattApi(), "foo", "bar"
    )
    sensor.update()
    assert sensor.state == 142.0
