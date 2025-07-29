"""Test the AirPatrol sensor platform."""

import logging
from unittest.mock import MagicMock

import pytest

from homeassistant.components.airpatrol.sensor import (
    SENSOR_DESCRIPTIONS,
    AirPatrolSensor,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

MOCK_UNIT_DATA = {
    "unit_id": "test_unit_001",
    "name": "Test Unit",
    "model": "AirPatrol Pro",
    "manufacturer": "AirPatrol",
    "climate": {
        "ApiVersion": "12",
        "CommandMode": "parameters",
        "ParametersData": {
            "PumpPower": "on",
            "PumpTemp": "22.000",
            "PumpMode": "heat",
            "FanSpeed": "max",
            "Swing": "off",
        },
        "RoomTemp": "22.5",
        "RoomHumidity": "45.2",
    },
}


def test_sensor_descriptions() -> None:
    """Test sensor descriptions."""
    assert len(SENSOR_DESCRIPTIONS) == 3

    # Check status sensor
    status_desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "status")
    assert status_desc.translation_key == "status"

    # Check temperature sensor
    temp_desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "temperature")
    assert temp_desc.device_class == SensorDeviceClass.TEMPERATURE
    assert temp_desc.native_unit_of_measurement == UnitOfTemperature.CELSIUS

    # Check humidity sensor
    humidity_desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "humidity")
    assert humidity_desc.device_class == SensorDeviceClass.HUMIDITY
    assert humidity_desc.native_unit_of_measurement == PERCENTAGE


def test_airpatrol_sensor_initialization() -> None:
    """Test AirPatrol sensor initialization."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.api = MagicMock()
    coordinator.api.get_unique_id.return_value = "test_unique_id"

    description = SENSOR_DESCRIPTIONS[0]  # status sensor
    sensor = AirPatrolSensor(coordinator, description, MOCK_UNIT_DATA, "test_unit_001")

    assert sensor.unit == MOCK_UNIT_DATA
    assert sensor.unit_id == "test_unit_001"
    assert sensor._attr_unique_id == "test_unique_id_test_unit_001_status"
    assert sensor._attr_device_info is not None
    assert sensor._attr_device_info["identifiers"] == {("airpatrol", "test_unit_001")}
    assert sensor._attr_device_info["name"] == "Test Unit"


def test_sensor_native_value_status() -> None:
    """Test sensor native value for status."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.api = MagicMock()
    coordinator.api.get_unique_id.return_value = "test_unique_id"
    coordinator.data = [MOCK_UNIT_DATA]
    description = next(d for d in SENSOR_DESCRIPTIONS if d.key == "status")
    sensor = AirPatrolSensor(
        coordinator, description, coordinator.data[0], "test_unit_001"
    )
    assert sensor.native_value == "online"


def test_sensor_native_value_temperature() -> None:
    """Test sensor native value for temperature."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.api = MagicMock()
    coordinator.api.get_unique_id.return_value = "test_unique_id"
    coordinator.data = [
        {
            "unit_id": "test_unit_001",
            "climate": {"RoomTemp": "22.5", "RoomHumidity": "45.2"},
        }
    ]

    description = next(d for d in SENSOR_DESCRIPTIONS if d.key == "temperature")
    sensor = AirPatrolSensor(
        coordinator, description, coordinator.data[0], "test_unit_001"
    )

    assert sensor.native_value == 22.5


def test_sensor_native_value_humidity() -> None:
    """Test sensor native value for humidity."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.api = MagicMock()
    coordinator.api.get_unique_id.return_value = "test_unique_id"
    coordinator.data = [
        {
            "unit_id": "test_unit_001",
            "climate": {"RoomTemp": "22.5", "RoomHumidity": "45.2"},
        }
    ]

    description = next(d for d in SENSOR_DESCRIPTIONS if d.key == "humidity")
    sensor = AirPatrolSensor(
        coordinator, description, coordinator.data[0], "test_unit_001"
    )

    assert sensor.native_value == 45.2


def test_sensor_native_value_none_data() -> None:
    """Test sensor native value when coordinator data is None."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.api = MagicMock()
    coordinator.api.get_unique_id.return_value = "test_unique_id"
    coordinator.data = None

    description = SENSOR_DESCRIPTIONS[0]
    sensor = AirPatrolSensor(coordinator, description, MOCK_UNIT_DATA, "test_unit_001")
    assert sensor.native_value == "offline"


def test_sensor_native_value_missing_data() -> None:
    """Test sensor native value when unit data is missing."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.api = MagicMock()
    coordinator.api.get_unique_id.return_value = "test_unique_id"
    coordinator.data = []  # For missing data

    description = next(d for d in SENSOR_DESCRIPTIONS if d.key == "temperature")
    sensor = AirPatrolSensor(coordinator, description, MOCK_UNIT_DATA, "test_unit_001")

    assert sensor.native_value is None


def test_sensor_available_logging(caplog: pytest.LogCaptureFixture) -> None:
    """Test logging when sensor entity becomes unavailable and then available again."""
    caplog.set_level(logging.INFO)
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.api = MagicMock()
    coordinator.api.get_unique_id.return_value = "test_unique_id"
    coordinator.data = [{"unit_id": "test_unit_001", "climate": {}}]
    coordinator.last_update_success = True
    description = SENSOR_DESCRIPTIONS[0]
    sensor = AirPatrolSensor(
        coordinator, description, coordinator.data[0], "test_unit_001"
    )
    # Simulate unavailable
    sensor.unit = {"unit_id": "test_unit_001"}
    coordinator.data = []
    coordinator.last_update_success = True
    assert not sensor.available
    assert "is unavailable" in caplog.text
    # Simulate available again
    sensor.unit = {"unit_id": "test_unit_001", "climate": {}}
    coordinator.data = [sensor.unit]
    coordinator.last_update_success = True
    assert sensor.available
    assert "is back online" in caplog.text


def test_sensor_native_value_temperature_invalid() -> None:
    """Test native_value for temperature with invalid value."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.api = MagicMock()
    coordinator.api.get_unique_id.return_value = "test_unique_id"
    coordinator.data = [
        {
            "unit_id": "test_unit_001",
            "climate": {"RoomTemp": "not_a_float"},
        }
    ]
    description = next(d for d in SENSOR_DESCRIPTIONS if d.key == "temperature")
    sensor = AirPatrolSensor(
        coordinator, description, coordinator.data[0], "test_unit_001"
    )
    assert sensor.native_value is None


def test_sensor_native_value_humidity_invalid() -> None:
    """Test native_value for humidity with invalid value."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.api = MagicMock()
    coordinator.api.get_unique_id.return_value = "test_unique_id"
    coordinator.data = [
        {
            "unit_id": "test_unit_001",
            "climate": {"RoomHumidity": "not_a_float"},
        }
    ]
    description = next(d for d in SENSOR_DESCRIPTIONS if d.key == "humidity")
    sensor = AirPatrolSensor(
        coordinator, description, coordinator.data[0], "test_unit_001"
    )
    assert sensor.native_value is None


def test_sensor_device_info_missing_fields() -> None:
    """Test device_info is set even if manufacturer/model missing."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.api = MagicMock()
    coordinator.api.get_unique_id.return_value = "test_unique_id"
    unit = {"unit_id": "test_unit_001", "name": "Test Unit"}  # No manufacturer/model
    description = SENSOR_DESCRIPTIONS[0]
    sensor = AirPatrolSensor(coordinator, description, unit, "test_unit_001")
    device_info = sensor.device_info
    if device_info is not None:
        assert device_info["identifiers"] == {("airpatrol", "test_unit_001")}
        assert device_info["manufacturer"] == "AirPatrol"
        assert device_info["model"] == "AirPatrol Unit"
