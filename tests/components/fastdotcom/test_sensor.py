"""Test the Fast.com component sensors."""

import pytest

from homeassistant.components.fastdotcom.sensor import (
    DownloadSpeedSensor,
    LoadedPingSensor,
    UnloadedPingSensor,
    UploadSpeedSensor,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfDataRate


# A simple dummy coordinator that mimics the real coordinator used by the integration.
class DummyCoordinator:
    """Dummy coordinator for testing Fast.com sensors."""

    def __init__(self, data):
        """Initialize dummy coordinator with provided test data."""
        self.data = data


@pytest.fixture
def dummy_coordinator():
    """Fixture that provides a dummy coordinator instance for testing."""
    data = {
        "download_speed": 100.0,
        "upload_speed": 50.0,
        "ping_loaded": 20.5,
        "ping_unloaded": 15.2,
    }
    return DummyCoordinator(data)


def test_download_speed_sensor(dummy_coordinator):
    """Test the DownloadSpeedSensor native_value and attributes."""
    entry_id = "test_entry"
    sensor = DownloadSpeedSensor(entry_id, dummy_coordinator)
    assert sensor.native_value == 100.0
    assert sensor._attr_native_unit_of_measurement == UnitOfDataRate.MEGABITS_PER_SECOND
    assert sensor._attr_device_class == SensorDeviceClass.DATA_RATE
    assert sensor._attr_state_class == SensorStateClass.MEASUREMENT


def test_upload_speed_sensor(dummy_coordinator):
    """Test the UploadSpeedSensor native_value and attributes."""
    entry_id = "test_entry"
    sensor = UploadSpeedSensor(entry_id, dummy_coordinator)
    assert sensor.native_value == 50.0
    assert sensor._attr_native_unit_of_measurement == UnitOfDataRate.MEGABITS_PER_SECOND
    assert sensor._attr_device_class == SensorDeviceClass.DATA_RATE
    assert sensor._attr_state_class == SensorStateClass.MEASUREMENT


def test_unloaded_ping_sensor(dummy_coordinator):
    """Test the UnloadedPingSensor native_value and attributes."""
    entry_id = "test_entry"
    sensor = UnloadedPingSensor(entry_id, dummy_coordinator)
    assert sensor.native_value == 15.2
    # Here you can optionally verify additional attributes (if set).
    assert sensor._attr_native_unit_of_measurement == "ms"
    assert sensor._attr_state_class == SensorStateClass.MEASUREMENT


def test_loaded_ping_sensor(dummy_coordinator):
    """Test the LoadedPingSensor native_value and attributes."""
    entry_id = "test_entry"
    sensor = LoadedPingSensor(entry_id, dummy_coordinator)
    assert sensor.native_value == 20.5
    # Optionally check additional attributes.
    assert sensor._attr_native_unit_of_measurement == "ms"
    assert sensor._attr_state_class == SensorStateClass.MEASUREMENT
