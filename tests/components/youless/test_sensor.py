"""Test the sensor classes for youless."""

from unittest.mock import MagicMock

import youless_api

from homeassistant.components.sensor import SensorStateClass
from homeassistant.components.youless.sensor import (
    CurrentPowerSensor,
    DeliveryMeterSensor,
    EnergyMeterSensor,
    GasSensor,
    WaterSensor,
)


def test_water_sensor():
    """Check the water sensor setup."""
    mock_coordinator = MagicMock(
        data=MagicMock(model="LS120", water_meter=youless_api.YoulessSensor(123.12, ""))
    )

    water_sensor = WaterSensor(mock_coordinator, "localhost")

    assert water_sensor.unique_id == "youless_localhost_water"
    assert water_sensor.device_info.get("manufacturer") == "YouLess"
    assert water_sensor.device_info.get("model") == "LS120"
    assert water_sensor.device_info.get("name") == "Water meter"
    assert water_sensor.name == "Water usage"
    assert water_sensor.native_value == 123.12
    assert water_sensor.available


def test_gas_sensor():
    """Check the gas sensor setup."""
    mock_coordinator = MagicMock(
        data=MagicMock(model="LS120", gas_meter=youless_api.YoulessSensor(829, ""))
    )

    water_sensor = GasSensor(mock_coordinator, "localhost")

    assert water_sensor.unique_id == "youless_localhost_gas"
    assert water_sensor.device_info.get("manufacturer") == "YouLess"
    assert water_sensor.device_info.get("model") == "LS120"
    assert water_sensor.device_info.get("name") == "Gas meter"
    assert water_sensor.native_value == 829
    assert water_sensor.available
    assert water_sensor.name == "Gas usage"


def test_current_power_sensor():
    """Check the current power sensor setup."""
    mock_coordinator = MagicMock(
        data=MagicMock(
            model="LS120", current_power_usage=youless_api.YoulessSensor(123.12, "")
        )
    )

    water_sensor = CurrentPowerSensor(mock_coordinator, "localhost")

    assert water_sensor.unique_id == "youless_localhost_usage"
    assert water_sensor.device_info.get("manufacturer") == "YouLess"
    assert water_sensor.device_info.get("model") == "LS120"
    assert water_sensor.device_info.get("name") == "Power usage"
    assert water_sensor.native_value == 123.12
    assert water_sensor.available
    assert water_sensor.name == "Power Usage"


def test_delivery_meter_sensor():
    """Check the delivery meter sensor setup."""
    mock_coordinator = MagicMock(
        data=MagicMock(
            model="LS120",
            delivery_meter=youless_api.DeliveryMeter(
                youless_api.YoulessSensor(1233, ""),
                youless_api.YoulessSensor(91822, ""),
            ),
        )
    )

    water_sensor = DeliveryMeterSensor(mock_coordinator, "localhost", "low")

    assert water_sensor.unique_id == "youless_localhost_delivery_low"
    assert water_sensor.device_info.get("manufacturer") == "YouLess"
    assert water_sensor.device_info.get("model") == "LS120"
    assert water_sensor.device_info.get("name") == "Energy delivery"
    assert water_sensor.native_value == 1233
    assert water_sensor.available
    assert water_sensor.name == "Energy delivery low"


def test_energy_meter_sensor():
    """Check the delivery meter sensor setup."""
    mock_coordinator = MagicMock(
        data=MagicMock(
            model="LS120",
            power_meter=youless_api.PowerMeter(
                youless_api.YoulessSensor(1233, ""),
                youless_api.YoulessSensor(91822, ""),
                youless_api.YoulessSensor(1233 + 91822, ""),
            ),
        )
    )

    water_sensor = EnergyMeterSensor(
        mock_coordinator, "localhost", "low", SensorStateClass.TOTAL_INCREASING
    )

    assert water_sensor.unique_id == "youless_localhost_power_low"
    assert water_sensor.device_info.get("manufacturer") == "YouLess"
    assert water_sensor.device_info.get("model") == "LS120"
    assert water_sensor.device_info.get("name") == "Energy usage"
    assert water_sensor.native_value == 1233
    assert water_sensor.available
    assert water_sensor.name == "Energy low"
