"""Test the Briiv sensor platform."""

from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components.briiv.const import SENSOR_TYPES
from homeassistant.components.briiv.sensor import BriivSensor
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature


@pytest.fixture
def mock_api():
    """Mock Briiv API."""
    api = AsyncMock()
    api.register_callback = Mock()
    api.remove_callback = Mock()
    return api


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    return Mock(data={"serial_number": "TEST123"})


async def test_sensor_initialization(mock_api, mock_config_entry) -> None:
    """Test sensor entity initialization."""
    temp_description = next(s for s in SENSOR_TYPES if s.key == "temp")
    sensor = BriivSensor(mock_api, temp_description, mock_config_entry, "TEST123")

    assert sensor.unique_id == "TEST123_temp"
    assert sensor.name is None  # Uses device name
    assert sensor.device_class == SensorDeviceClass.TEMPERATURE
    assert sensor.native_unit_of_measurement == UnitOfTemperature.CELSIUS
    assert sensor.state_class == SensorStateClass.MEASUREMENT
    assert sensor.native_value is None

    mock_api.register_callback.assert_called_once_with(sensor._handle_update)


async def test_sensor_update_callback(mock_api, mock_config_entry) -> None:
    """Test sensor update callback."""
    # Test temperature sensor
    temp_description = next(s for s in SENSOR_TYPES if s.key == "temp")
    temp_sensor = BriivSensor(mock_api, temp_description, mock_config_entry, "TEST123")

    await temp_sensor._handle_update({"serial_number": "TEST123", "temp": 22.5})
    assert temp_sensor.native_value == 22.5

    # Test humidity sensor
    humid_description = next(s for s in SENSOR_TYPES if s.key == "humid")
    humid_sensor = BriivSensor(
        mock_api, humid_description, mock_config_entry, "TEST123"
    )

    await humid_sensor._handle_update({"serial_number": "TEST123", "humid": 45})
    assert humid_sensor.native_value == 45

    # Test PM2.5 sensor
    pm25_description = next(s for s in SENSOR_TYPES if s.key == "pm2_5")
    pm25_sensor = BriivSensor(mock_api, pm25_description, mock_config_entry, "TEST123")

    await pm25_sensor._handle_update({"serial_number": "TEST123", "pm2_5": 12})
    assert pm25_sensor.native_value == 12


async def test_sensor_wrong_serial(mock_api, mock_config_entry) -> None:
    """Test sensor ignores updates for wrong serial number."""
    temp_description = next(s for s in SENSOR_TYPES if s.key == "temp")
    sensor = BriivSensor(mock_api, temp_description, mock_config_entry, "TEST123")

    await sensor._handle_update({"serial_number": "WRONG123", "temp": 22.5})
    assert sensor.native_value is None


async def test_sensor_missing_value(mock_api, mock_config_entry) -> None:
    """Test sensor handles missing value in update."""
    temp_description = next(s for s in SENSOR_TYPES if s.key == "temp")
    sensor = BriivSensor(mock_api, temp_description, mock_config_entry, "TEST123")

    await sensor._handle_update(
        {
            "serial_number": "TEST123",
            "humid": 45,  # Different sensor value
        }
    )
    assert sensor.native_value is None


async def test_sensor_remove_callback(mock_api, mock_config_entry) -> None:
    """Test callback removal when sensor is removed."""
    temp_description = next(s for s in SENSOR_TYPES if s.key == "temp")
    sensor = BriivSensor(mock_api, temp_description, mock_config_entry, "TEST123")

    await sensor.async_will_remove_from_hass()
    mock_api.remove_callback.assert_called_once_with(sensor._handle_update)


async def test_all_sensor_types(mock_api, mock_config_entry) -> None:
    """Test all defined sensor types initialize correctly."""
    for description in SENSOR_TYPES:
        sensor = BriivSensor(mock_api, description, mock_config_entry, "TEST123")
        assert sensor.unique_id == f"TEST123_{description.key}"
        assert sensor.device_class is not None
        assert sensor.native_unit_of_measurement is not None
        assert sensor.state_class == SensorStateClass.MEASUREMENT
