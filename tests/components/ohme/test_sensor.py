import pytest
from unittest.mock import MagicMock
from custom_components.ohme.sensor import VoltageSensor


@pytest.fixture
def mock_coordinator():
    """Fixture for creating a mock coordinator."""
    coordinator = MagicMock()
    return coordinator


@pytest.fixture
def voltage_sensor(mock_coordinator):
    """Fixture for creating a VoltageSensor instance."""
    hass = MagicMock()
    client = MagicMock()
    return VoltageSensor(mock_coordinator, hass, client)


def test_voltage_sensor_native_value_with_data(voltage_sensor, mock_coordinator):
    """Test native_value when coordinator has data."""
    mock_coordinator.data = {"power": {"volt": 230}}
    assert voltage_sensor.native_value == 230


def test_voltage_sensor_native_value_no_data(voltage_sensor, mock_coordinator):
    """Test native_value when coordinator has no data."""
    mock_coordinator.data = None
    assert voltage_sensor.native_value is None


def test_voltage_sensor_native_value_no_power_data(voltage_sensor, mock_coordinator):
    """Test native_value when coordinator has no power data."""
    mock_coordinator.data = {"power": None}
    assert voltage_sensor.native_value is None
