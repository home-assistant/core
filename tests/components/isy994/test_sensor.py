"""Test the ISY994 sensor platform."""

from unittest.mock import MagicMock

from homeassistant.components.isy994.sensor import (
    ISY_CONTROL_TO_STATE_CLASS,
    UOM_TO_DEVICE_CLASS,
    ISYSensorEntity,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass


def test_mappings() -> None:
    """Test that mappings are correctly defined."""
    # Test UOM to Device Class
    assert UOM_TO_DEVICE_CLASS["4"] == SensorDeviceClass.TEMPERATURE
    assert UOM_TO_DEVICE_CLASS["33"] == SensorDeviceClass.ENERGY
    assert UOM_TO_DEVICE_CLASS["143"] == SensorDeviceClass.VOLUME_FLOW_RATE
    assert UOM_TO_DEVICE_CLASS["69"] == SensorDeviceClass.WATER
    assert UOM_TO_DEVICE_CLASS["24"] == SensorDeviceClass.PRECIPITATION_INTENSITY

    # Test Control to State Class
    assert ISY_CONTROL_TO_STATE_CLASS["TPW"] == SensorStateClass.TOTAL_INCREASING
    assert ISY_CONTROL_TO_STATE_CLASS["CPW"] == SensorStateClass.MEASUREMENT


def test_isy_sensor_entity_properties() -> None:
    """Test ISYSensorEntity property logic."""
    mock_node = MagicMock()
    mock_node.isy.uuid = "12345"
    mock_node.address = "1 2 3 1"
    mock_node.name = "Test Node"
    mock_node.status = 100
    mock_node.uom = "4"  # Celsius
    mock_node.prec = "1"
    mock_node.status_events.subscribe.return_value = MagicMock()

    entity = ISYSensorEntity(mock_node)

    # Should use UOM mapping
    assert entity.device_class == SensorDeviceClass.TEMPERATURE
    assert entity.state_class == SensorStateClass.MEASUREMENT

    # Should respect explicit attribute
    entity._attr_device_class = SensorDeviceClass.HUMIDITY
    assert entity.device_class == SensorDeviceClass.HUMIDITY

    # Test state_class for TOTAL_INCREASING
    mock_node.uom = "33"  # Energy
    entity._attr_device_class = None
    entity._attr_state_class = None
    assert entity.device_class == SensorDeviceClass.ENERGY
    assert entity.state_class == SensorStateClass.TOTAL_INCREASING
