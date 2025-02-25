"""Test the Tilt Hydrometer sensors."""

from unittest.mock import Mock

import pytest

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.tilt_pi.const import DOMAIN
from homeassistant.components.tilt_pi.coordinator import TiltPiDataUpdateCoordinator
from homeassistant.components.tilt_pi.model import TiltHydrometerData
from homeassistant.components.tilt_pi.sensor import (
    TiltGravitySensor,
    TiltTemperatureSensor,
)
from homeassistant.const import UnitOfTemperature


@pytest.fixture
def mock_tilt_data() -> TiltHydrometerData:
    """Create mock tilt data."""
    return TiltHydrometerData(
        mac_id="00:1A:2B:3C:4D:5E",
        color="Purple",
        temperature=68.0,
        gravity=1.052,
    )


@pytest.fixture
def mock_coordinator(mock_tilt_data) -> TiltPiDataUpdateCoordinator:
    """Create a mock coordinator."""
    coordinator = Mock()
    coordinator.data = [mock_tilt_data]
    return coordinator


async def test_tilt_temperature_sensor(
    mock_coordinator: TiltPiDataUpdateCoordinator,
    mock_tilt_data: TiltHydrometerData,
) -> None:
    """Test the temperature sensor."""
    sensor = TiltTemperatureSensor(mock_coordinator, mock_tilt_data)

    assert sensor.unique_id == f"{mock_tilt_data.mac_id}_temperature"
    assert sensor.device_class == SensorDeviceClass.TEMPERATURE
    assert sensor.state_class == SensorStateClass.MEASUREMENT
    assert sensor.native_unit_of_measurement == UnitOfTemperature.FAHRENHEIT
    assert sensor.native_value == 68.0
    assert sensor.has_entity_name is True

    # Test device info
    assert sensor.device_info["identifiers"] == {(DOMAIN, mock_tilt_data.mac_id)}
    assert sensor.device_info["name"] == "Tilt Purple"
    assert sensor.device_info["manufacturer"] == "Tilt Hydrometer"
    assert sensor.device_info["model"] == "Purple Tilt Hydrometer"

    # Test with no data
    mock_coordinator.data = []
    assert sensor.native_value is None


async def test_tilt_gravity_sensor(
    mock_coordinator: TiltPiDataUpdateCoordinator,
    mock_tilt_data: TiltHydrometerData,
) -> None:
    """Test the gravity sensor."""
    sensor = TiltGravitySensor(mock_coordinator, mock_tilt_data)

    assert sensor.unique_id == f"{mock_tilt_data.mac_id}_gravity"
    assert sensor.state_class == SensorStateClass.MEASUREMENT
    assert sensor.native_unit_of_measurement == "SG"
    assert sensor.icon == "mdi:water"
    assert sensor.native_value == 1.052
    assert sensor.has_entity_name is True

    # Test device info
    assert sensor.device_info["identifiers"] == {(DOMAIN, mock_tilt_data.mac_id)}
    assert sensor.device_info["name"] == "Tilt Purple"

    # Test with no data
    mock_coordinator.data = []
    assert sensor.native_value is None
