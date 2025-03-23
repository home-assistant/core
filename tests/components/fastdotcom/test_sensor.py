"""Test the Fast.com component sensors using the unified FastdotcomSensor."""

import pytest

from homeassistant.components.fastdotcom.sensor import SENSOR_TYPES, FastdotcomSensor
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfDataRate, UnitOfTime
from homeassistant.helpers.device_registry import DeviceInfo


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
        "unloaded_ping": 15.2,
        "loaded_ping": 20.5,
    }
    return DummyCoordinator(data)


@pytest.fixture
def dummy_device_info():
    """Fixture that provides dummy device info for testing."""
    return DeviceInfo(
        identifiers={("fastdotcom", "test_entry")},
        name="Fast.com",
        manufacturer="Fast.com",
        model="Speed Test Integration",
    )


def test_download_speed_sensor(dummy_coordinator, dummy_device_info):
    """Test the Download Speed sensor native_value and attributes."""
    entry_id = "test_entry"
    description = next(desc for desc in SENSOR_TYPES if desc.key == "download_speed")
    sensor = FastdotcomSensor(
        entry_id, dummy_coordinator, description, dummy_device_info
    )
    assert sensor.native_value == 100.0
    assert description.native_unit_of_measurement == UnitOfDataRate.MEGABITS_PER_SECOND
    assert description.device_class == SensorDeviceClass.DATA_RATE
    assert description.state_class == SensorStateClass.MEASUREMENT


def test_upload_speed_sensor(dummy_coordinator, dummy_device_info):
    """Test the Upload Speed sensor native_value and attributes."""
    entry_id = "test_entry"
    description = next(desc for desc in SENSOR_TYPES if desc.key == "upload_speed")
    sensor = FastdotcomSensor(
        entry_id, dummy_coordinator, description, dummy_device_info
    )
    assert sensor.native_value == 50.0
    assert description.native_unit_of_measurement == UnitOfDataRate.MEGABITS_PER_SECOND
    assert description.device_class == SensorDeviceClass.DATA_RATE
    assert description.state_class == SensorStateClass.MEASUREMENT


def test_unloaded_ping_sensor(dummy_coordinator, dummy_device_info):
    """Test the Unloaded Ping sensor native_value and attributes."""
    entry_id = "test_entry"
    description = next(desc for desc in SENSOR_TYPES if desc.key == "unloaded_ping")
    sensor = FastdotcomSensor(
        entry_id, dummy_coordinator, description, dummy_device_info
    )
    assert sensor.native_value == 15.2
    assert description.native_unit_of_measurement == UnitOfTime.MILLISECONDS
    assert description.state_class == SensorStateClass.MEASUREMENT


def test_loaded_ping_sensor(dummy_coordinator, dummy_device_info):
    """Test the Loaded Ping sensor native_value and attributes."""
    entry_id = "test_entry"
    description = next(desc for desc in SENSOR_TYPES if desc.key == "loaded_ping")
    sensor = FastdotcomSensor(
        entry_id, dummy_coordinator, description, dummy_device_info
    )
    assert sensor.native_value == 20.5
    assert description.native_unit_of_measurement == UnitOfTime.MILLISECONDS
    assert description.state_class == SensorStateClass.MEASUREMENT
